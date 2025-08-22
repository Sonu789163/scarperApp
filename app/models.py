from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class TranscriptReq(BaseModel):
    video_url: str = Field(description="YouTube video URL")
    video_id: Optional[str] = Field(default=None, description="YouTube video ID (if not in URL)")
    languages: List[str] = Field(default=["en"], description="Preferred languages for transcript")
    translate_to: Optional[str] = Field(default=None, description="Language to translate transcript to")
    try_youtube_data_api: bool = Field(default=False, description="Try YouTube Data API as fallback")
    stt_fallback: bool = Field(default=False, description="Use open-source STT fallback (faster-whisper) when captions unavailable")


class TranscriptSegment(BaseModel):
    start: float = Field(description="Start time in seconds")
    duration: float = Field(description="Duration in seconds")
    text: str = Field(description="Transcript text for this segment")


class TranscriptRes(BaseModel):
    video_id: str
    title: Optional[str] = None
    language: str
    segments: List[TranscriptSegment]
    total_duration: float
    source: str = Field(description="Source: 'youtube_transcript_api' | 'youtube_data_api'")


class FramesReq(BaseModel):
    video_url: str = Field(description="YouTube video URL")
    video_id: Optional[str] = Field(default=None, description="YouTube video ID (if not in URL)")
    method: Literal["interval", "scenedetect"] = Field(description="Frame extraction method")
    interval_seconds: Optional[float] = Field(default=5.0, description="Interval between frames (for interval method)")
    max_frames: int = Field(default=100, ge=1, le=500, description="Maximum number of frames to extract")
    return_zip: bool = Field(default=True, description="Return frames as ZIP file")
    content_threshold: Optional[float] = Field(default=27.0, description="Content threshold for scene detection")
    include_listing: bool = Field(default=True, description="Include JSON listing of frames")


class FrameItem(BaseModel):
    timestamp: float = Field(description="Frame timestamp in seconds")
    frame_number: int = Field(description="Sequential frame number")
    filename: str = Field(description="Frame filename")


class FramesRes(BaseModel):
    video_id: str
    title: Optional[str] = None
    total_frames: int
    frames: List[FrameItem]
    method: str
    video_duration: float
    extraction_time: float
    zip_filename: Optional[str] = Field(default=None, description="ZIP filename if returned as ZIP")
