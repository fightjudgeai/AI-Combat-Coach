"""
vision/pipeline.py
Orchestrates the full CV pipeline for a single fight video.

CLI usage:
    python -m vision.pipeline \\
        --source "s3://my-bucket/fights/jones_vs_gane.mp4" \\
        --fighter-id "uuid-of-fighter-to-tag" \\
        --corner left            # which corner is our fighter? left|right|auto
        --interval 2.0           # sample every N seconds (default 2)
        --device cuda            # cuda | cpu

    python -m vision.pipeline \\
        --source "https://www.youtube.com/watch?v=XXXXXXXXXXX" \\
        --fighter-id "uuid" \\
        --corner auto

Env vars required:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

import cv2

from .attribute import FighterAccumulator
from .aggression import build_summary
from .classifier import FightClassifier, FrameState
from .detect import FighterObservation, PoseDetector
from .extract import iter_frames, video_duration
from .events import FightEvent
from .ingest import detect_source_type, resolve_video
from .writer import (
    complete_job, create_job, fail_job,
    insert_events, update_fighter_attributes, upsert_summary,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Corner assignment
# ---------------------------------------------------------------------------

def assign_corners(
    obs_list: list[FighterObservation],
    corner: str,
    first_frame_seen: Dict[int, float],
) -> tuple[Optional[FighterObservation], Optional[FighterObservation]]:
    """
    Return (target_obs, opponent_obs).
    corner: 'left' | 'right' | 'auto'
    """
    if len(obs_list) == 0:
        return None, None

    if len(obs_list) == 1:
        return obs_list[0], None

    a, b = obs_list[0], obs_list[1]

    if corner == "auto":
        # First frame each track_id appeared — assign corners by initial x position
        a_init_cx = first_frame_seen.get(a.track_id, a.cx)
        b_init_cx = first_frame_seen.get(b.track_id, b.cx)
        # Lower initial cx → left/red corner
        if a_init_cx <= b_init_cx:
            target, opponent = (a, b) if corner != "right" else (b, a)
        else:
            target, opponent = (b, a) if corner != "right" else (a, b)
        return target, opponent

    # Explicit: find the one on the correct side in this frame
    left_obs  = a if a.cx <= b.cx else b
    right_obs = b if a.cx <= b.cx else a

    if corner == "left":
        return left_obs, right_obs
    return right_obs, left_obs


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(
    source: str,
    fighter_id: Optional[str],
    corner: str = "auto",
    interval: float = 2.0,
    device: str = "cuda",
) -> Dict:
    workdir: Optional[Path] = None
    job_id: Optional[str] = None
    source_type = detect_source_type(source)

    try:
        job_id = create_job(source, source_type, fighter_id)
        log.info("Job %s started | source=%s corner=%s", job_id, source, corner)

        # ------------------------------------------------------------------
        # 1. Resolve video to local path
        # ------------------------------------------------------------------
        if source_type != "local":
            workdir = Path(tempfile.mkdtemp(prefix="fjai_vision_"))
        video_path, _ = resolve_video(source, workdir=workdir)
        duration = video_duration(video_path)
        log.info("Video resolved: %s  duration=%.1fs", video_path, duration)

        # ------------------------------------------------------------------
        # 2. Load detector
        # ------------------------------------------------------------------
        detector = PoseDetector(device=device)
        accumulator = FighterAccumulator(target_track_id=-1)  # target assigned first frame
        classifier  = FightClassifier(sample_interval=interval)
        all_events: List[FightEvent] = []
        cx_snapshots: List[tuple[float, float]] = []
        first_frame_seen: Dict[int, float] = {}
        target_track_id: Optional[int] = None
        frames_sampled = 0

        # ------------------------------------------------------------------
        # 3. Frame loop
        # ------------------------------------------------------------------
        cap_tmp = cv2.VideoCapture(str(video_path))
        frame_w = int(cap_tmp.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap_tmp.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap_tmp.release()

        for ts, frame in iter_frames(video_path, sample_interval_secs=interval):
            obs_list = detector.detect(frame, frame_w, frame_h)
            frames_sampled += 1

            # Register first-frame positions for auto corner assignment
            for o in obs_list:
                if o.track_id not in first_frame_seen:
                    first_frame_seen[o.track_id] = o.cx

            target_obs, opp_obs = assign_corners(obs_list, corner, first_frame_seen)

            if target_obs is None:
                continue

            # Lock target track_id on first successful assignment
            if target_track_id is None:
                target_track_id = target_obs.track_id
                accumulator = FighterAccumulator(target_track_id)
                log.info("Locked target track_id=%d at t=%.1fs", target_track_id, ts)

            # Only accumulate frames where our target is visible
            if target_obs.track_id == target_track_id:
                accumulator.ingest(ts, target_obs, opp_obs)
                cx_snapshots.append((ts, target_obs.cx))

                # Classifier: build FrameState and detect events
                fs = FrameState(
                    ts=ts, obs=target_obs, opp=opp_obs,
                    frame_w=frame_w, frame_h=frame_h,
                )
                frame_events = classifier.ingest(fs)
                all_events.extend(frame_events)

            if frames_sampled % 100 == 0:
                log.info("Processed %d frames | t=%.1fs", frames_sampled, ts)

        # Flush any pending position state
        all_events.extend(classifier.flush(duration))

        # ------------------------------------------------------------------
        # 4. Compute style attributes + event summary
        # ------------------------------------------------------------------
        attrs   = accumulator.compute()
        summary = build_summary(all_events, cx_snapshots, duration, interval)
        log.info("Attributes computed: %s", attrs)
        log.info("Events detected: %d total", len(all_events))

        # ------------------------------------------------------------------
        # 5. Write to DB
        # ------------------------------------------------------------------
        raw_out = {**attrs, "event_count": len(all_events), "summary": summary}
        complete_job(job_id, frames_sampled, duration, raw_out)

        if fighter_id:
            if all_events:
                insert_events(job_id, fighter_id, all_events)
                upsert_summary(job_id, fighter_id, summary)
            if attrs:
                # Backfill grappling_first + finish_urgency from event data
                grappling_total = (
                    summary["takedowns_landed"] +
                    summary["submission_attempts"] +
                    summary["time_in_half_guard"] +
                    summary["time_in_full_guard"]
                )
                striking_total = (
                    summary["punches_attempted"] +
                    summary["kicks_attempted"]
                )
                attrs["grappling_first"] = grappling_total > striking_total
                attrs["finish_urgency"]  = round(
                    min(
                        (summary["knockdowns_scored"] * 15 +
                         summary["submission_attempts"] * 10 +
                         summary["takedowns_landed"] * 5)
                        / max(duration / 60, 1) / 3, 100
                    ), 2
                )
                update_fighter_attributes(fighter_id, attrs)
            log.info("Fighter %s updated", fighter_id)

        return {
            "job_id":         job_id,
            "frames_sampled": frames_sampled,
            "events":         len(all_events),
            "attrs":          attrs,
            "summary":        summary,
        }

    except Exception as exc:
        log.exception("Pipeline failed: %s", exc)
        if job_id:
            fail_job(job_id, str(exc))
        raise

    finally:
        if workdir and workdir.exists():
            shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="FJAI fight video CV pipeline")
    p.add_argument("--source",     required=True, help="local path, s3://, or YouTube URL")
    p.add_argument("--fighter-id", default=None,  help="UUID of fighter to tag in DB")
    p.add_argument("--corner",     default="auto", choices=["left", "right", "auto"],
                   help="Which corner is the target fighter? (default: auto)")
    p.add_argument("--interval",   type=float, default=2.0,
                   help="Frame sample interval in seconds (default: 2.0)")
    p.add_argument("--device",     default="cuda", help="cuda | cpu (default: cuda)")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    result = run(
        source=args.source,
        fighter_id=args.fighter_id,
        corner=args.corner,
        interval=args.interval,
        device=args.device,
    )
    print(result)
