"""Plot 3D trajectories from a skeleton JSON produced by process_svo.py.

Default: index fingertip (kp[8]) trajectory in left-camera coordinates.
Saves <stem>_trajectory.png next to the JSON.
"""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# MediaPipe joint indices
JOINTS = {"wrist": 0, "thumb_tip": 4, "index_tip": 8, "middle_tip": 12,
          "ring_tip": 16, "pinky_tip": 20}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("json", type=Path)
    p.add_argument("--hand", default="Left", choices=["Left", "Right"])
    p.add_argument("--joint", default="index_tip", choices=list(JOINTS))
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    data = json.loads(args.json.read_text())
    joint_idx = JOINTS[args.joint]

    pts_world = []
    pts_wrist = []
    ts = []
    for fr in data["frames"]:
        for h in fr["hands"]:
            if h["label"] != args.hand:
                continue
            pts_world.append(h["keypoints_camera_m"][joint_idx])
            pts_wrist.append(h["keypoints_wrist_m"][joint_idx])
            ts.append(fr["timestamp_ns"])
            break

    if not pts_world:
        print(f"No '{args.hand}' hand observations found.")
        return

    pts_world = np.array(pts_world)
    pts_wrist = np.array(pts_wrist)
    ts = np.array(ts)
    ts = (ts - ts[0]) / 1e9  # seconds since first obs

    fig = plt.figure(figsize=(14, 6))

    ax1 = fig.add_subplot(121, projection="3d")
    sc = ax1.scatter(pts_world[:, 0], pts_world[:, 2], -pts_world[:, 1],
                     c=ts, cmap="viridis", s=20)
    ax1.plot(pts_world[:, 0], pts_world[:, 2], -pts_world[:, 1],
             color="gray", alpha=0.4, lw=0.8)
    ax1.set_xlabel("X (m, right+)")
    ax1.set_ylabel("Z (m, forward+)")
    ax1.set_zlabel("-Y (m, up+)")
    ax1.set_title(f"{args.hand} {args.joint} in CAMERA frame")
    plt.colorbar(sc, ax=ax1, label="time (s)", shrink=0.6)

    ax2 = fig.add_subplot(122, projection="3d")
    sc2 = ax2.scatter(pts_wrist[:, 0], pts_wrist[:, 2], -pts_wrist[:, 1],
                      c=ts, cmap="viridis", s=20)
    ax2.plot(pts_wrist[:, 0], pts_wrist[:, 2], -pts_wrist[:, 1],
             color="gray", alpha=0.4, lw=0.8)
    ax2.set_xlabel("dX (m)")
    ax2.set_ylabel("dZ (m)")
    ax2.set_zlabel("-dY (m)")
    ax2.set_title(f"{args.hand} {args.joint} relative to WRIST")
    plt.colorbar(sc2, ax=ax2, label="time (s)", shrink=0.6)

    fig.suptitle(f"{args.json.name}\nN={len(pts_world)} observations  "
                 f"duration={ts[-1]:.2f}s")
    plt.tight_layout()

    out = args.out or args.json.with_name(args.json.stem + f"_trajectory_{args.joint}.png")
    fig.savefig(out, dpi=120)
    print(f"saved {out}")

    # Console summary
    print("\nCAMERA frame stats (m):")
    print(f"  X range: {pts_world[:,0].min():+.3f}  -> {pts_world[:,0].max():+.3f}  "
          f"(span {pts_world[:,0].ptp():.3f})")
    print(f"  Y range: {pts_world[:,1].min():+.3f}  -> {pts_world[:,1].max():+.3f}  "
          f"(span {pts_world[:,1].ptp():.3f})")
    print(f"  Z range: {pts_world[:,2].min():+.3f}  -> {pts_world[:,2].max():+.3f}  "
          f"(span {pts_world[:,2].ptp():.3f})")


if __name__ == "__main__":
    main()
