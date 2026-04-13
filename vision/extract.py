"""
vision/extract.py
Sample frames from a fight video at a fixed interval (default 2 s).
Yields (timestamp_secs, numpy BGR frame) tuples.

Falls back to an ffmpeg subprocess for codecs unsupported by the OpenCV
build inside the container (e.g. AV1 / VP9 when the system libavcodec
lacks software-decode support).
"""
from __future__ import annotations

import json
import logging
import subprocess
import cv2
import numpy as np
from pathlib import Path
from typing import Generator, Tuple

log = logging.getLogger(__name__)


def iter_frames(
    video_path: Path,
    sample_interval_secs: float = 2.0,
) -> Generator[Tuple[float, np.ndarray], None, None]:
    """
    Yield (timestamp_secs, frame) at every sample_interval_secs.

    Tries cv2.VideoCapture first.  If the first cap.read() fails (codec
    not supported — common with AV1 on CPU-only containers), silently
    falls back to an ffmpeg pipe which handles AV1/VP9/HEVC etc.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = max(1, int(fps * sample_interval_secs))

    # -- probe first frame to detect unsupported codec --
    ret, first_frame = cap.read()
    if not ret:
        cap.release()
        log.info("cv2 cannot decode %s (likely AV1/VP9) — falling back to ffmpeg", video_path.name)
        yield from _iter_frames_ffmpeg(video_path, sample_interval_secs)
        return

    # frame 0 — yield if it lands on a sample boundary (frame_interval may be >1)
    if 0 % frame_interval == 0:
        yield 0.0, first_frame

    frame_idx = 1
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            ts = frame_idx / fps
            yield ts, frame
        frame_idx += 1

    cap.release()


def _iter_frames_ffmpeg(
    video_path: Path,
    sample_interval_secs: float = 2.0,
) -> Generator[Tuple[float, np.ndarray], None, None]:
    """
    Decode video via ``ffmpeg`` subprocess and yield sampled BGR frames.

    Uses ``-vf fps=<rate>`` so only the frames we need are decoded;
    the full bitstream is still read but we avoid converting every frame.
    """
    # -- probe dimensions via ffprobe --
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "v:0", str(video_path),
    ]
    try:
        probe = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        stream = json.loads(probe.stdout).get("streams", [{}])[0]
        width  = int(stream.get("width",  1280))
        height = int(stream.get("height", 720))
    except Exception as exc:
        log.warning("ffprobe failed for %s: %s", video_path.name, exc)
        return

    if width <= 0 or height <= 0:
        log.warning("ffprobe returned invalid dimensions (%dx%d) for %s — skipping", width, height, video_path.name)
        return

    frame_size = width * height * 3  # BGR24 bytes per frame
    fps_out    = 1.0 / sample_interval_secs  # e.g. 0.5 for 2-s interval

    cmd = [
        "ffmpeg", "-v", "quiet",
        "-i", str(video_path),
        "-vf", f"fps={fps_out}",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frame_idx = 0
    try:
        while True:
            raw = proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                break
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3)).copy()
            ts = frame_idx * sample_interval_secs
            yield ts, frame
            frame_idx += 1
    finally:
        proc.stdout.close()
        proc.wait()


def video_duration(video_path: Path) -> float:
    """Return video duration in seconds (ffprobe fallback if cv2 fails)."""
    cap = cv2.VideoCapture(str(video_path))
    fps         = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()

    if fps and frame_count:
        return frame_count / fps

    # cv2 gave zeros — use ffprobe (handles AV1 / VP9 duration metadata)
    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", str(video_path),
    ]
    try:
        probe = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        fmt = json.loads(probe.stdout).get("format", {})
        return float(fmt.get("duration", 0.0))
    except Exception:
        return 0.0
