from typing import Annotated
import time
import shutil
import tempfile
from pathlib import Path
import os

from fastapi import APIRouter, File, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse

from .clients import http_client
from .config import settings
from .schemas import CaptionResponse, HealthResponse, OcrResponse, ScrapeRequest, ScrapeResponse
from .scraper import scrape_url
from .models import TranscriptReq, TranscriptRes, TranscriptSegment, FramesReq, FramesRes, FrameItem
from .yt_utils import (
    extract_video_id, get_transcript_via_lib, get_transcript_via_youtube_data_api,
    download_video_to_tmp, download_audio_to_tmp, transcribe_audio_via_faster_whisper,
    duration_seconds, extract_frames_interval,
    detect_scenes_and_midpoints, extract_frames_at_timestamps, make_zip
)


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/healthz")
async def healthz():
    return {"ok": True}


@router.post("/proxy/ocr", response_model=OcrResponse)
async def proxy_ocr(file: Annotated[UploadFile, File(...)]) -> OcrResponse:
    try:
        async with http_client() as client:
            files = {"file": (file.filename, await file.read(), file.content_type or "application/octet-stream")}
            resp = await client.post(settings.ocr_api_url, files=files)
            resp.raise_for_status()
            data = resp.json()
            return OcrResponse(text=data.get("text", ""))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OCR upstream error: {exc}")


@router.post("/proxy/caption", response_model=CaptionResponse)
async def proxy_caption(file: Annotated[UploadFile, File(...)]) -> CaptionResponse:
    try:
        async with http_client() as client:
            files = {"file": (file.filename, await file.read(), file.content_type or "application/octet-stream")}
            resp = await client.post(settings.caption_api_url, files=files)
            resp.raise_for_status()
            data = resp.json()
            return CaptionResponse(caption=data.get("caption", ""))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Caption upstream error: {exc}")


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape(payload: ScrapeRequest) -> ScrapeResponse:
    try:
        result = await scrape_url(payload.url, headless=payload.headless)
        return ScrapeResponse(**result)
    except HTTPException as e:
        raise e
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scrape error: {exc}")


@router.post("/transcript", response_model=TranscriptRes)
async def get_transcript(payload: TranscriptReq) -> TranscriptRes:
    start_time = time.time()
    try:
        video_id = extract_video_id(payload.video_url, payload.video_id)
        # 1) Try library captions
        result = get_transcript_via_lib(video_id, payload.languages, payload.translate_to)
        if result:
            items, language_code = result
            segments = []
            total_duration = 0.0
            for entry in items:
                start = float(entry.get('start', 0))
                duration = float(entry.get('duration', 0))
                text = entry.get('text', '')
                segments.append(TranscriptSegment(start=start, duration=duration, text=text))
                total_duration = max(total_duration, start + duration)
            return TranscriptRes(
                video_id=video_id,
                language=language_code or 'unknown',
                segments=segments,
                total_duration=total_duration,
                source='youtube-transcript-api'
            )
        # 2) STT fallback if allowed
        if payload.stt_fallback:
            try:
                audio_path, tmp_dir = download_audio_to_tmp(video_id)
                items, lang = transcribe_audio_via_faster_whisper(audio_path, language_hint=payload.translate_to or (payload.languages[0] if payload.languages else None))
                segments = []
                total_duration = 0.0
                for entry in items:
                    start = float(entry.get('start', 0))
                    duration = float(entry.get('duration', 0))
                    text = entry.get('text', '')
                    segments.append(TranscriptSegment(start=start, duration=duration, text=text))
                    total_duration = max(total_duration, start + duration)
                return TranscriptRes(
                    video_id=video_id,
                    language=lang,
                    segments=segments,
                    total_duration=total_duration,
                    source='stt'
                )
            except ImportError as e:
                raise HTTPException(status_code=400, detail=f"STT fallback not available: {e}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"STT fallback error: {e}")
            finally:
                if 'tmp_dir' in locals() and tmp_dir and os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir)
        # 3) Otherwise 404
        raise HTTPException(status_code=404, detail="Transcript not available for this video")
    except HTTPException as e:
        raise e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcript error: {exc}")


@router.post("/frames", response_model=FramesRes)
async def extract_frames(payload: FramesReq) -> FramesRes:
    start_time = time.time()
    temp_dir = None
    video_path = None
    try:
        if payload.method == "interval" and payload.interval_seconds <= 0:
            raise HTTPException(status_code=400, detail="interval_seconds must be > 0")
        if payload.max_frames > 500:
            raise HTTPException(status_code=413, detail="max_frames cannot exceed 500")
        video_id = extract_video_id(payload.video_url, payload.video_id)
        video_path, temp_dir = download_video_to_tmp(video_id, cookies=payload.cookies, use_android_client=payload.use_android_client)
        video_duration = duration_seconds(video_path)
        if video_duration <= 0:
            raise HTTPException(status_code=500, detail="Could not determine video duration")
        frames_dir = os.path.join(temp_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        if payload.method == "interval":
            timestamps = extract_frames_interval(video_path, frames_dir, payload.interval_seconds, payload.max_frames)
        elif payload.method == "scenedetect":
            scene_midpoints = detect_scenes_and_midpoints(video_path, payload.content_threshold)
            timestamps = extract_frames_at_timestamps(video_path, frames_dir, scene_midpoints, payload.max_frames)
        else:
            raise HTTPException(status_code=400, detail="Invalid method")
        frames = []
        for i, timestamp in enumerate(timestamps):
            frames.append(FrameItem(timestamp=timestamp, frame_number=i, file_path=os.path.join(frames_dir, f"frame_{i:04d}.jpg")))
        extraction_time = time.time() - start_time
        if payload.return_zip:
            zip_path = make_zip(frames_dir, f"frames_{video_id}")
            return FileResponse(zip_path, media_type="application/zip", filename=f"frames_{video_id}.zip")
        return FramesRes(
            video_id=video_id,
            total_frames=len(frames),
            frames=frames,
            method=payload.method,
            video_duration=video_duration,
            extraction_time=extraction_time
        )
    except HTTPException as e:
        raise e
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Frame extraction error: {exc}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

