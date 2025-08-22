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
    download_video_to_tmp, duration_seconds, extract_frames_interval,
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
    try:
        vid = extract_video_id(payload.video_url, payload.video_id)

        # First try youtube-transcript-api
        try:
            source, segs = get_transcript_via_lib(vid, payload.languages, payload.translate_to)
            segments = [TranscriptSegment(start=s["start"], duration=s["duration"], text=s["text"]) for s in segs]
            return TranscriptRes(
                video_id=vid, 
                source=source, 
                segments=segments,
                language=payload.languages[0] if payload.languages else "en",
                total_duration=max([s.start + s.duration for s in segments]) if segments else 0.0
            )
        except Exception as e:
            # Optional fallback to YouTube Data API if env + flag are set
            if payload.try_youtube_data_api and os.getenv("YOUTUBE_API_KEY"):
                segs = get_transcript_via_youtube_data_api(vid)
                if segs:
                    segments = [TranscriptSegment(**s) for s in segs]
                    return TranscriptRes(
                        video_id=vid, 
                        source="youtube_data_api", 
                        segments=segments,
                        language=payload.languages[0] if payload.languages else "en",
                        total_duration=max([s.start + s.duration for s in segments]) if segments else 0.0
                    )

            raise HTTPException(status_code=404, detail=f"Transcript not available: {str(e)}")
    except HTTPException as e:
        raise e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcript error: {exc}")


@router.post("/frames")
async def frames(req: FramesReq):
    vid = extract_video_id(req.video_url, req.video_id)
    tmpdir, video_path = None, None
    try:
        tmpdir, video_path = download_video_to_tmp(vid)
        frames_dir = os.path.join(tmpdir, "frames")
        if req.method == "interval":
            extracted = extract_frames_interval(video_path, frames_dir, req.interval_seconds, req.max_frames)
        else:
            mids = detect_scenes_and_midpoints(video_path, req.content_threshold, req.max_frames)
            extracted = extract_frames_at_timestamps(video_path, frames_dir, mids)

        items = [FrameItem(timestamp=t, frame_number=i, filename=f) for i, (t, f) in enumerate(extracted, start=1)]

        if req.return_zip:
            zip_base = os.path.join(tmpdir, f"{vid}_frames")
            zip_path = make_zip(frames_dir, zip_base)
            # Stream back the zip; also include JSON listing in header (optional)
            headers = {}
            if hasattr(req, 'include_listing') and req.include_listing:
                headers["X-Frames-Listing"] = os.path.basename(zip_path)  # simple marker
            return FileResponse(zip_path, media_type="application/zip", filename=os.path.basename(zip_path))

        # Otherwise JSON-only
        return FramesRes(
            video_id=vid,
            method=req.method,
            frames=items,
            total_frames=len(items),
            video_duration=duration_seconds(video_path),
            extraction_time=0.0  # We'll calculate this if needed
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmpdir and os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)

