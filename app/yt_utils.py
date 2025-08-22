import os
import re
import tempfile
import zipfile
import time
from pathlib import Path
from typing import List, Optional, Tuple
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from scenedetect import SceneManager, open_video, ContentDetector
import cv2
import subprocess
import json


def extract_video_id(video_url: str, video_id: Optional[str] = None) -> str:
    """Extract YouTube video ID from URL or use provided ID."""
    if video_id:
        return video_id
    
    # Common YouTube URL patterns
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, video_url)
        if match:
            return match.group(1)
    
    raise ValueError("Invalid YouTube URL or could not extract video ID")


def get_transcript_via_lib(video_id: str, languages: List[str] = None, translate_to: str = None) -> Optional[dict]:
    """Get transcript using youtube-transcript-api with fallbacks."""
    if languages is None:
        languages = ["en"]
    
    try:
        # Try to get transcript in preferred languages
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # First try to get transcript in preferred language
        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                if translate_to and translate_to != lang:
                    transcript = transcript.translate(translate_to)
                return transcript
            except (NoTranscriptFound, TranscriptsDisabled):
                continue
        
        # Fallback to any available transcript
        try:
            transcript = transcript_list.find_transcript(transcript_list)
            if translate_to:
                transcript = transcript.translate(translate_to)
            return transcript
        except (NoTranscriptFound, TranscriptsDisabled):
            pass
            
    except Exception as e:
        print(f"Error getting transcript via lib: {e}")
    
    return None


def get_transcript_via_youtube_data_api(video_id: str) -> Optional[dict]:
    """Get transcript via YouTube Data API (requires OAuth setup)."""
    # TODO: Implement OAuth flow for captions.download
    # This requires setting up OAuth 2.0 credentials and handling authentication
    return None


def download_video_to_tmp(video_id: str) -> Tuple[str, str]:
    """Download video to temporary directory using yt-dlp."""
    temp_dir = tempfile.mkdtemp(prefix=f"yt_{video_id}_")
    
    ydl_opts = {
        'format': 'best[height<=720]',  # Limit to 720p for faster processing
        'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    
    # Find the downloaded file
    video_files = list(Path(temp_dir).glob(f"{video_id}.*"))
    if not video_files:
        raise FileNotFoundError("Video file not found after download")
    
    return str(video_files[0]), temp_dir


def duration_seconds(video_path: str) -> float:
    """Get video duration using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"Error getting duration: {e}")
        return 0.0


def extract_frames_interval(video_path: str, out_dir: str, interval_seconds: float, max_frames: int) -> List[float]:
    """Extract frames at regular intervals using FFmpeg."""
    os.makedirs(out_dir, exist_ok=True)
    timestamps = []
    
    # Calculate frame intervals
    duration = duration_seconds(video_path)
    if duration <= 0:
        return timestamps
    
    # Generate timestamps
    current_time = 0.0
    frame_count = 0
    
    while current_time < duration and frame_count < max_frames:
        output_file = os.path.join(out_dir, f"frame_{frame_count:04d}.jpg")
        
        cmd = [
            'ffmpeg', '-y', '-ss', str(current_time), '-i', video_path,
            '-vframes', '1', '-q:v', '2', output_file
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            timestamps.append(current_time)
            frame_count += 1
        except subprocess.CalledProcessError as e:
            print(f"Error extracting frame at {current_time}s: {e}")
        
        current_time += interval_seconds
    
    return timestamps


def detect_scenes_and_midpoints(video_path: str, content_threshold: float = 27.0) -> List[float]:
    """Detect scenes and return midpoints using PySceneDetect."""
    try:
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=content_threshold))
        scene_manager.detect_scenes(video=video)
        
        scenes = scene_manager.get_scene_list()
        midpoints = []
        
        for start, end in scenes:
            midpoint = (start.get_seconds() + end.get_seconds()) / 2
            midpoints.append(midpoint)
        
        return midpoints
    except Exception as e:
        print(f"Error detecting scenes: {e}")
        return []


def extract_frames_at_timestamps(video_path: str, out_dir: str, timestamps: List[float], max_frames: int) -> List[float]:
    """Extract frames at specific timestamps."""
    os.makedirs(out_dir, exist_ok=True)
    extracted_timestamps = []
    
    for i, timestamp in enumerate(timestamps[:max_frames]):
        output_file = os.path.join(out_dir, f"frame_{i:04d}.jpg")
        
        cmd = [
            'ffmpeg', '-y', '-ss', str(timestamp), '-i', video_path,
            '-vframes', '1', '-q:v', '2', output_file
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            extracted_timestamps.append(timestamp)
        except subprocess.CalledProcessError as e:
            print(f"Error extracting frame at {timestamp}s: {e}")
    
    return extracted_timestamps


def make_zip(source_dir: str, zip_basename: str) -> str:
    """Create ZIP file from source directory."""
    zip_path = f"{zip_basename}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)
    
    return zip_path
