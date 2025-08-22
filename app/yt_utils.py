import os, re, tempfile, subprocess, json, math, shutil, uuid
from typing import List, Optional, Tuple
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
from scenedetect.frame_timecode import FrameTimecode
import cv2
from pathlib import Path

YTCLEAN = re.compile(r"[^A-Za-z0-9_\-]")

def extract_video_id(video_url: Optional[str], video_id: Optional[str]) -> str:
    if video_id:
        return YTCLEAN.sub("", video_id)
    if not video_url:
        raise ValueError("Provide video_url or video_id")
    # Support youtu.be/<id> and youtube.com/watch?v=<id>
    m = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", str(video_url))
    if not m:
        raise ValueError("Could not extract video_id from URL")
    return m.group(1)

def get_transcript_via_lib(vid: str, languages: List[str], translate_to: Optional[str]):
    # Try original languages first
    try:
        segments = YouTubeTranscriptApi.get_transcript(vid, languages=languages)
        return "youtube_transcript_api", segments
    except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript):
        # Try translated if requested
        if translate_to:
            try:
                seg = YouTubeTranscriptApi.get_transcript(vid, languages=languages, preserve_formatting=True)
                # If translation tracks exist separately:
                trans = YouTubeTranscriptApi.list_transcripts(vid)
                tr = trans.find_transcript(languages=languages)
                tr_en = tr.translate(translate_to)
                return "youtube_transcript_api", tr_en.fetch()
            except Exception:
                pass
        raise

def get_transcript_via_youtube_data_api(vid: str) -> Optional[List[dict]]:
    """
    NOTE: YouTube Data API often requires OAuth for captions.download and
    does not guarantee access to auto-generated captions.
    This is a best-effort placeholder (returns None).
    If you own the channel, implement OAuth and captions.download here.
    """
    return None

def download_video_to_tmp(vid: str) -> Tuple[str, str]:
    """Download best MP4 into a temp dir with yt-dlp; return (dir, video_path)."""
    tmpdir = tempfile.mkdtemp(prefix=f"yt_{vid}_")
    outtmpl = os.path.join(tmpdir, "%(id)s.%(ext)s")
    # Build format: prefer mp4
    ytdlp_cmd = [
        "yt-dlp",
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "-o", outtmpl,
        f"https://www.youtube.com/watch?v={vid}",
        "--no-warnings",
        "--quiet"
    ]
    subprocess.run(ytdlp_cmd, check=True)
    # Find downloaded file
    video_files = list(Path(tmpdir).glob(f"{vid}.*"))
    if not video_files:
        raise RuntimeError("Download failed")
    return tmpdir, str(video_files[0])

def duration_seconds(video_path: str) -> float:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, check=True
    )
    return float(probe.stdout.strip())

def extract_frames_interval(video_path: str, out_dir: str, interval_s: float, max_frames: int) -> List[Tuple[float, str]]:
    """Extract 1 frame every interval_s seconds using ffmpeg."""
    os.makedirs(out_dir, exist_ok=True)
    # We'll seek each timestamp and grab 1 frame to keep accurate timestamps.
    dur = duration_seconds(video_path)
    timestamps = [round(t, 3) for t in frange(0.0, dur, interval_s)]
    timestamps = timestamps[:max_frames]
    results = []
    for idx, t in enumerate(timestamps, start=1):
        outfile = os.path.join(out_dir, f"frame_{idx:05d}.jpg")
        cmd = ["ffmpeg", "-ss", str(t), "-i", video_path, "-frames:v", "1", "-q:v", "2", "-y", outfile]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        results.append((t, os.path.basename(outfile)))
    return results

def frange(start: float, stop: float, step: float):
    t = start
    while t <= stop:
        yield t
        t += step

def detect_scenes_and_midpoints(video_path: str, threshold: float, cap: int) -> List[float]:
    """Use PySceneDetect content detector to get scene boundaries, return midpoints (seconds)."""
    vm = VideoManager([video_path])
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=threshold))
    vm.set_downscale_factor()  # auto
    vm.start()
    sm.detect_scenes(frame_source=vm)
    scene_list = sm.get_scene_list(vm.get_base_timecode())
    vm.release()

    midpoints = []
    for (start, end) in scene_list:
        start_s = start.get_seconds()
        end_s = end.get_seconds()
        mid = round((start_s + end_s) / 2.0, 3)
        midpoints.append(mid)
    if not midpoints:
        # fallback: single midpoint
        midpoints = [round(duration_seconds(video_path) / 2.0, 3)]
    return midpoints[:cap]

def extract_frames_at_timestamps(video_path: str, out_dir: str, timestamps: List[float]) -> List[Tuple[float, str]]:
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for idx, t in enumerate(timestamps, start=1):
        outfile = os.path.join(out_dir, f"frame_{idx:05d}.jpg")
        cmd = ["ffmpeg", "-ss", str(t), "-i", video_path, "-frames:v", "1", "-q:v", "2", "-y", outfile]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        results.append((t, os.path.basename(outfile)))
    return results

def make_zip(source_dir: str, zip_basename: str) -> str:
    # Returns path to created zip file (on disk)
    zip_path = shutil.make_archive(zip_basename, "zip", root_dir=source_dir)
    return zip_path
