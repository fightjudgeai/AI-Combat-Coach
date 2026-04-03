"""
vision/extract.py
Sample frames from a fight video at a fixed interval (default 2 s).
Yields (timestamp_secs, numpy BGR frame) tuples.
"""
from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
from typing import Generator, Tuple


def iter_frames(
    video_path: Path,
    sample_interval_secs: float = 2.0,
) -> Generator[Tuple[float, np.ndarray], None, None]:
    """
    Yield (timestamp_secs, frame) at every sample_interval_secs.
    Skips corrupt / unreadable frames silently.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_interval = max(1, int(fps * sample_interval_secs))

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            ts = frame_idx / fps
            yield ts, frame
        frame_idx += 1

    cap.release()


def video_duration(video_path: Path) -> float:
    """Return video duration in seconds."""
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return frame_count / fps if fps else 0.0
