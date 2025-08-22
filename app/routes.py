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
    """Health check endpoint for Render."""
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scrape error: {exc}")


@router.post("/transcript", response_model=TranscriptRes)
async def get_transcript(payload: TranscriptReq) -> TranscriptRes:
    """Get YouTube video transcript."""
    start_time = time.time()
    
    try:
        # Extract video ID
        video_id = extract_video_id(payload.video_url, payload.video_id)
        
        # Try youtube-transcript-api first
        transcript = get_transcript_via_lib(
            video_id, 
            payload.languages, 
            payload.translate_to
        )
        
        if transcript:
            # Convert to our format
            segments = []
            total_duration = 0
            
            for entry in transcript:
                start = entry.get('start', 0)
                duration = entry.get('duration', 0)
                text = entry.get('text', '')
                
                segments.append(TranscriptSegment(
                    start=start,
                    duration=duration,
                    text=text
                ))
                
                total_duration = max(total_duration, start + duration)
            
            return TranscriptRes(
                video_id=video_id,
                language=transcript.language_code if hasattr(transcript, 'language_code') else 'en',
                segments=segments,
                total_duration=total_duration,
                source='youtube-transcript-api'
            )
        
        # Fallback to YouTube Data API if requested
        if payload.try_youtube_data_api:
            transcript = get_transcript_via_youtube_data_api(video_id)
            if transcript:
                # Handle Data API response format
                pass
        
        # No transcript available
        raise HTTPException(
            status_code=404, 
            detail="Transcript not available for this video"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcript error: {exc}")


@router.post("/frames", response_model=FramesRes)
async def extract_frames(payload: FramesReq) -> FramesRes:
    """Extract frames from YouTube video."""
    start_time = time.time()
    temp_dir = None
    video_path = None
    
    try:
        # Validate parameters
        if payload.method == "interval" and payload.interval_seconds <= 0:
            raise HTTPException(status_code=400, detail="interval_seconds must be > 0")
        
        if payload.max_frames > 500:
            raise HTTPException(status_code=413, detail="max_frames cannot exceed 500")
        
        # Extract video ID
        video_id = extract_video_id(payload.video_url, payload.video_id)
        
        # Download video
        video_path, temp_dir = download_video_to_tmp(video_id)
        video_duration = duration_seconds(video_path)
        
        if video_duration <= 0:
            raise HTTPException(status_code=500, detail="Could not determine video duration")
        
        # Create frames directory
        frames_dir = os.path.join(temp_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # Extract frames based on method
        if payload.method == "interval":
            timestamps = extract_frames_interval(
                video_path, frames_dir, payload.interval_seconds, payload.max_frames
            )
        elif payload.method == "scenedetect":
            scene_midpoints = detect_scenes_and_midpoints(
                video_path, payload.content_threshold
            )
            timestamps = extract_frames_at_timestamps(
                video_path, frames_dir, scene_midpoints, payload.max_frames
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid method")
        
        # Create frame items
        frames = []
        for i, timestamp in enumerate(timestamps):
            frames.append(FrameItem(
                timestamp=timestamp,
                frame_number=i,
                file_path=os.path.join(frames_dir, f"frame_{i:04d}.jpg")
            ))
        
        extraction_time = time.time() - start_time
        
        # Return ZIP if requested
        if payload.return_zip:
            zip_path = make_zip(frames_dir, f"frames_{video_id}")
            return FileResponse(
                zip_path,
                media_type="application/zip",
                filename=f"frames_{video_id}.zip"
            )
        
        # Return JSON response
        return FramesRes(
            video_id=video_id,
            total_frames=len(frames),
            frames=frames,
            method=payload.method,
            video_duration=video_duration,
            extraction_time=extraction_time
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Frame extraction error: {exc}")
    finally:
        # Cleanup temporary files
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

