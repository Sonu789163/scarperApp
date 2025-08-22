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

# STT fallback (optional)
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    WhisperModel = None


def extract_video_id(video_url: str, video_id: Optional[str] = None) -> str:
    """Extract YouTube video ID from URL or use provided ID."""
    if video_id:
        return video_id
    
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


def _fetch_with_optional_translate(transcript_obj, translate_to: Optional[str]) -> Tuple[List[dict], str]:
    """Fetch transcript, translating if possible; fall back to original on translation failure."""
    original_lang = getattr(transcript_obj, "language_code", "unknown")
    if translate_to:
        try:
            t = transcript_obj.translate(translate_to)
            items = t.fetch()
            lang_code = getattr(t, "language_code", translate_to)
            return items, lang_code
        except Exception:
            # Best-effort fallback to original language
            try:
                items = transcript_obj.fetch()
                return items, original_lang
            except Exception:
                raise
    # No translation requested
    items = transcript_obj.fetch()
    return items, original_lang


def get_transcript_via_lib(video_id: str, languages: List[str] = None, translate_to: str = None) -> Optional[Tuple[List[dict], str]]:
    """Get transcript using youtube-transcript-api.
    Tries manual, then auto-generated captions; optional translation is best-effort.
    Returns (items, language_code) or None if not available.
    """
    languages = languages or ["en", "en-US", "en-GB"]
    try:
        t_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # 1) Manual preferred
        try:
            manual = t_list.find_manually_created_transcript(languages)
            return _fetch_with_optional_translate(manual, translate_to)
        except Exception:
            pass
        # 2) Auto preferred
        try:
            auto = t_list.find_generated_transcript(languages)
            return _fetch_with_optional_translate(auto, translate_to)
        except Exception:
            pass
        # 3) Any available (manual or auto)
        for tr in t_list:
            try:
                return _fetch_with_optional_translate(tr, translate_to)
            except Exception:
                continue
        return None
    except (NoTranscriptFound, TranscriptsDisabled):
        return None
    except Exception:
        # Last-chance simple path
        try:
            items = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
            return items, languages[0]
        except Exception:
            return None


def get_transcript_via_youtube_data_api(video_id: str) -> Optional[dict]:
    """Get transcript via YouTube Data API (requires OAuth setup)."""
    return None


def _ydl_download(url: str, outtmpl: str, format_str: str, cookies: Optional[str], use_android_client: bool) -> None:
    ydl_opts = {
        'format': format_str,
        'outtmpl': outtmpl,
        'quiet': True,
    }
    if cookies:
        ydl_opts['http_headers'] = { 'Cookie': cookies }
    if use_android_client:
        ydl_opts.setdefault('extractor_args', {}).setdefault('youtube', {})['player_client'] = ['android']
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_video_to_tmp(video_id: str, cookies: Optional[str] = None, use_android_client: bool = True) -> Tuple[str, str]:
    temp_dir = tempfile.mkdtemp(prefix=f"yt_{video_id}_")
    url = f"https://www.youtube.com/watch?v={video_id}"
    outtmpl = os.path.join(temp_dir, '%(id)s.%(ext)s')
    # Try requested client first, then fall back to default web client
    try:
        _ydl_download(url, outtmpl, 'best[height<=720]', cookies, use_android_client)
    except Exception:
        _ydl_download(url, outtmpl, 'best[height<=720]', cookies, False)
    video_files = list(Path(temp_dir).glob(f"{video_id}.*"))
    if not video_files:
        raise FileNotFoundError("Video file not found after download")
    return str(video_files[0]), temp_dir


def download_audio_to_tmp(video_id: str, cookies: Optional[str] = None, use_android_client: bool = True) -> Tuple[str, str]:
    temp_dir = tempfile.mkdtemp(prefix=f"yta_{video_id}_")
    url = f"https://www.youtube.com/watch?v={video_id}"
    outtmpl = os.path.join(temp_dir, '%(id)s.%(ext)s')
    def _run(use_android: bool):
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        }
        if cookies:
            ydl_opts['http_headers'] = { 'Cookie': cookies }
        if use_android:
            ydl_opts.setdefault('extractor_args', {}).setdefault('youtube', {})['player_client'] = ['android']
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    # Try requested client, then web
    try:
        _run(use_android_client)
    except Exception:
        _run(False)
    audio_files = list(Path(temp_dir).glob(f"{video_id}.mp3"))
    if not audio_files:
        any_audio = list(Path(temp_dir).glob(f"{video_id}.*"))
        if not any_audio:
            raise FileNotFoundError("Audio file not found after download")
        return str(any_audio[0]), temp_dir
    return str(audio_files[0]), temp_dir


def transcribe_audio_via_faster_whisper(audio_path: str, language_hint: Optional[str] = None) -> Tuple[List[dict], str]:
    if not FASTER_WHISPER_AVAILABLE:
        raise ImportError("faster-whisper not available. Install with: pip install faster-whisper")
    
    # Use small model by default for CPU
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, language=language_hint, vad_filter=True)
    items = []
    total = 0.0
    for seg in segments:
        start = float(seg.start)
        end = float(seg.end)
        text = seg.text.strip()
        items.append({"start": start, "duration": max(0.0, end - start), "text": text})
        total = max(total, end)
    return items, (info.language or (language_hint or "unknown"))


def duration_seconds(video_path: str) -> float:
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def extract_frames_interval(video_path: str, out_dir: str, interval_seconds: float, max_frames: int) -> List[float]:
    os.makedirs(out_dir, exist_ok=True)
    timestamps = []
    duration = duration_seconds(video_path)
    if duration <= 0:
        return timestamps
    current_time = 0.0
    frame_count = 0
    while current_time < duration and frame_count < max_frames:
        output_file = os.path.join(out_dir, f"frame_{frame_count:04d}.jpg")
        cmd = ['ffmpeg', '-y', '-ss', str(current_time), '-i', video_path, '-vframes', '1', '-q:v', '2', output_file]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            timestamps.append(current_time)
            frame_count += 1
        except subprocess.CalledProcessError:
            pass
        current_time += interval_seconds
    return timestamps


def detect_scenes_and_midpoints(video_path: str, content_threshold: float = 27.0) -> List[float]:
    try:
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=content_threshold))
        scene_manager.detect_scenes(video=video)
        scenes = scene_manager.get_scene_list()
        return [(s.get_seconds() + e.get_seconds()) / 2 for s, e in scenes]
    except Exception:
        return []


def extract_frames_at_timestamps(video_path: str, out_dir: str, timestamps: List[float], max_frames: int) -> List[float]:
    os.makedirs(out_dir, exist_ok=True)
    extracted = []
    for i, ts in enumerate(timestamps[:max_frames]):
        output_file = os.path.join(out_dir, f"frame_{i:04d}.jpg")
        cmd = ['ffmpeg', '-y', '-ss', str(ts), '-i', video_path, '-vframes', '1', '-q:v', '2', output_file]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            extracted.append(ts)
        except subprocess.CalledProcessError:
            pass
    return extracted


def make_zip(source_dir: str, zip_basename: str) -> str:
    zip_path = f"{zip_basename}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)
    return zip_path
