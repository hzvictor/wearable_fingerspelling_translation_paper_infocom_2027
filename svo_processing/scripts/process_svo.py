"""End-to-end: ZED SVO2 -> 3D hand skeleton JSON + overlay MP4.

Usage:
    python scripts/process_svo.py \
        --svo /Users/houzhen/Downloads/HD720_SN38429607_15-10-59.svo2 \
        --calib calib/SN38429607.conf \
        --out  outputs/

Outputs (per input file):
    outputs/<stem>_skeleton.json     per-frame hand observations
    outputs/<stem>_overlay.mp4       left-eye video + 2D skeleton + 3D HUD
    outputs/<stem>_stats.json        summary stats

Coordinate system:
    Left-camera optical center is origin. OpenCV convention:
      +X right, +Y down, +Z forward (into the scene). Units: meters.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# Allow `python scripts/process_svo.py` to find the src/ package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calibration import load_calib
from src.svo_io import SvoReader
from src.stereo_hands import StereoHandTracker, FINGERTIPS

import mediapipe as mp
_HC = mp.solutions.hands.HAND_CONNECTIONS


def draw_overlay(img: np.ndarray, obs_list) -> np.ndarray:
    """Draw 2D skeleton + per-hand wrist distance + 3D index-tip pos."""
    vis = img.copy()
    h, w = vis.shape[:2]
    # Connections
    for obs in obs_list:
        color = (0, 255, 255) if obs.label == "Left" else (255, 0, 255)
        for a, b in _HC:
            pa, pb = obs.kp_pixel_L[a], obs.kp_pixel_L[b]
            cv2.line(vis, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), color, 2)
        for (u, v) in obs.kp_pixel_L:
            cv2.circle(vis, (int(u), int(v)), 3, color, -1)

        wrist_z = obs.wrist_camera_m[2]
        idx_tip = obs.kp_camera_m[FINGERTIPS["index"]]
        wrist_u, wrist_v = obs.kp_pixel_L[0]
        cv2.putText(vis, f"{obs.label} z={wrist_z:.2f}m",
                    (int(wrist_u) - 30, int(wrist_v) + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        cv2.putText(vis, f" idx=({idx_tip[0]:+.2f},{idx_tip[1]:+.2f},{idx_tip[2]:+.2f})",
                    (int(wrist_u) - 30, int(wrist_v) + 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    return vis


def obs_to_dict(obs) -> dict:
    return {
        "label": obs.label,
        "score_L": obs.score_L,
        "score_R": obs.score_R,
        "keypoints_camera_m":  obs.kp_camera_m.tolist(),
        "keypoints_wrist_m":   obs.kp_wrist_m.tolist(),
        "keypoints_pixel_L":   obs.kp_pixel_L.tolist(),
        "keypoints_pixel_R":   obs.kp_pixel_R.tolist(),
        "wrist_camera_m":      obs.wrist_camera_m.tolist(),
        "reproj_err_px_L":     obs.reproj_err_px_L.tolist(),
        "reproj_err_px_R":     obs.reproj_err_px_R.tolist(),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--svo", type=Path, required=True)
    p.add_argument("--calib", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--resolution", default="HD")
    p.add_argument("--max-frames", type=int, default=None)
    p.add_argument("--video-fps", type=float, default=30.0)
    p.add_argument("--codec", default="mp4v")
    args = p.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.svo.stem
    out_json   = args.out / f"{stem}_skeleton.json"
    out_video  = args.out / f"{stem}_overlay.mp4"
    out_stats  = args.out / f"{stem}_stats.json"

    print(f"[load]  calib  : {args.calib}")
    calib = load_calib(args.calib, resolution=args.resolution)
    print(f"        K_L diag(fx,fy)= ({calib.K_L[0,0]:.2f}, {calib.K_L[1,1]:.2f})  "
          f"baseline={calib.baseline_m*1000:.2f}mm  res={calib.resolution}")

    print(f"[open]  svo    : {args.svo}")
    reader = SvoReader(args.svo)
    print(f"        topics : video={reader.video_topic}  imu={reader.imu_topic}")

    frames_out = []
    counts = dict(total=0, both_eyes_hand=0, left_hand=0, right_hand=0, two_hand=0)
    residuals = []
    z_values = []
    writer = None
    t0 = time.time()

    with StereoHandTracker(calib) as tracker:
        for idx, ts_ns, left, right in reader.iter_frames():
            if args.max_frames is not None and counts["total"] >= args.max_frames:
                break
            obs_list = tracker.process_frame(left, right)

            counts["total"] += 1
            if obs_list:
                counts["both_eyes_hand"] += 1
                labels = [o.label for o in obs_list]
                if "Left" in labels:  counts["left_hand"] += 1
                if "Right" in labels: counts["right_hand"] += 1
                if len(obs_list) >= 2: counts["two_hand"] += 1
                for o in obs_list:
                    residuals.extend(o.reproj_err_px_L.tolist())
                    residuals.extend(o.reproj_err_px_R.tolist())
                    z_values.append(o.wrist_camera_m[2])

            frame_record = {
                "frame_idx": idx,
                "timestamp_ns": ts_ns,
                "hands": [obs_to_dict(o) for o in obs_list],
            }
            frames_out.append(frame_record)

            vis = draw_overlay(left, obs_list)
            cv2.putText(vis, f"frame {idx}  hands={len(obs_list)}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            if writer is None:
                h, w = left.shape[:2]
                writer = cv2.VideoWriter(
                    str(out_video),
                    cv2.VideoWriter_fourcc(*args.codec),
                    args.video_fps, (w, h))
            writer.write(vis)

            if counts["total"] % 30 == 0:
                elapsed = time.time() - t0
                print(f"  [{counts['total']:4d}]  {counts['total']/elapsed:.1f} fps  "
                      f"both-eyes-hand={counts['both_eyes_hand']}")

    if writer is not None:
        writer.release()
    elapsed = time.time() - t0

    res = np.array(residuals) if residuals else np.zeros(0)
    z   = np.array(z_values) if z_values else np.zeros(0)
    stats = {
        "file":            str(args.svo),
        "calib":           str(args.calib),
        "resolution":      calib.resolution,
        "baseline_m":      calib.baseline_m,
        "total_frames":    counts["total"],
        "frames_with_stereo_hand": counts["both_eyes_hand"],
        "left_hand_frames":  counts["left_hand"],
        "right_hand_frames": counts["right_hand"],
        "two_hand_frames":   counts["two_hand"],
        "detection_rate":    counts["both_eyes_hand"] / max(counts["total"], 1),
        "elapsed_sec":       elapsed,
        "processing_fps":    counts["total"] / max(elapsed, 1e-9),
        "reproj_err_px": {
            "n":     int(res.size),
            "mean":  float(res.mean()) if res.size else None,
            "median":float(np.median(res)) if res.size else None,
            "p95":   float(np.percentile(res, 95)) if res.size else None,
            "max":   float(res.max()) if res.size else None,
        },
        "wrist_z_m": {
            "n":      int(z.size),
            "min":    float(z.min()) if z.size else None,
            "max":    float(z.max()) if z.size else None,
            "median": float(np.median(z)) if z.size else None,
        },
    }

    with open(out_json, "w") as f:
        json.dump({"meta": stats, "frames": frames_out}, f, indent=2)
    with open(out_stats, "w") as f:
        json.dump(stats, f, indent=2)

    print("\n=== done ===")
    print(json.dumps(stats, indent=2))
    print(f"\nJSON:    {out_json}")
    print(f"Overlay: {out_video}")
    print(f"Stats:   {out_stats}")


if __name__ == "__main__":
    main()
