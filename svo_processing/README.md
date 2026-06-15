# svo_processing — ZED 2i SVO2 → 3D Hand Skeleton Pipeline

Mac-friendly stereo hand-tracking from ZED 2i recordings. Bypasses the
ZED SDK entirely (it requires CUDA / NVIDIA, which doesn't exist on macOS).
Produces metric 3D hand keypoints suitable for downstream virtual-IMU
synthesis and KD teacher signals in the INFOCOM 2027 paper.

## What this folder does

```
SVO2 file ──┐
            ├─→ MCAP container parsed by `mcap` Python lib (no ZED SDK)
            ├─→ 4-JPEG strip layout decoded to YUYV → BGR (1280×720, 30 fps, left+right)
            ├─→ MediaPipe Hands on BOTH eyes (M5 Pro GPU via Metal)
            ├─→ Match hands across eyes by handedness label
            ├─→ cv2.undistortPoints + cv2.triangulatePoints
            └─→ 21 metric 3D keypoints per hand (left-camera frame, meters)
```

## Why we bypass the ZED SDK

The official ZED SDK requires CUDA + NVIDIA. macOS — including Apple Silicon
(M-series) — is not supported. We avoid it by:

1. **MCAP**: SVO2 is just an MCAP container (open ROS standard) — open-source `mcap`
   Python lib reads it.
2. **JPEG video**: ZED's `zed_sdk_encoded` payload is 4 grayscale JPEGs stacked
   vertically into a YUYV (YUV 4:2:2) packed buffer (reverse-engineered, see
   `src/svo_io.py`).
3. **Factory calibration**: Fetched as plain INI from Stereolabs' public URL
   `https://www.stereolabs.com/developers/calib/?SN=<serial>` — no SDK needed.
4. **Stereo math**: Classic computer vision via OpenCV (`undistortPoints`,
   `triangulatePoints`). No proprietary code path.

This gives us a fully reproducible pipeline that any reviewer can run.

## Folder layout

```
svo_processing/
├── README.md                    ← this file
├── .venv/                       ← Python 3.12 venv (mcap, mediapipe, opencv, av, matplotlib, numpy)
├── calib/
│   └── SN38429607.conf          ← factory calibration for OUR ZED 2i (SN 38429607)
├── src/
│   ├── __init__.py
│   ├── calibration.py           ← parse .conf → K matrices, R/T, P matrices
│   ├── svo_io.py                ← SVO2/MCAP reader + JPEG-strip-YUYV decoder + IMU iterator
│   └── stereo_hands.py          ← MediaPipe on L+R, handedness matching, triangulation
├── scripts/
│   ├── process_svo.py           ← MAIN ENTRY: SVO2 → skeleton JSON + overlay MP4
│   ├── inspect_svo.py           ← debug: list MCAP channels + dump header JSON
│   └── plot_trajectory.py       ← 3D trajectory plot from a skeleton JSON
└── outputs/
    └── (*_skeleton.json, *_overlay.mp4, *_stats.json, *_trajectory_*.png)
```

## Usage

All commands assume you're cd'd into this folder. The venv has all deps.

### Inspect a SVO2 file's structure

```bash
./.venv/bin/python scripts/inspect_svo.py /path/to/recording.svo2
```

Prints MCAP channels, per-channel message counts, and the embedded calibration
JSON header.

### Run the full pipeline (default)

```bash
./.venv/bin/python scripts/process_svo.py \
    --svo /path/to/recording.svo2 \
    --calib calib/SN38429607.conf \
    --out outputs/
```

Optional flags:
- `--resolution HD` (HD720, default), `FHD`, `2K`, `VGA`
- `--max-frames N` to truncate (debug)
- `--video-fps 30.0` for the overlay MP4

Outputs (per input file `<stem>.svo2`):
- `<stem>_skeleton.json` — per-frame 21 keypoints × hand × 3D + 2D + residuals
- `<stem>_overlay.mp4`   — left eye + skeleton drawn + distance HUD
- `<stem>_stats.json`    — summary (detection rate, residuals, z-range)

### Plot a 3D trajectory of one fingertip

```bash
./.venv/bin/python scripts/plot_trajectory.py \
    outputs/<stem>_skeleton.json --hand Left --joint index_tip
```

Saves a side-by-side 3D plot: **camera-frame** trajectory (left subplot) and
**wrist-relative** trajectory (right subplot), time-colored from start to end.

Joints available: `wrist`, `thumb_tip`, `index_tip`, `middle_tip`, `ring_tip`,
`pinky_tip`. To plot other joints (e.g., proximal phalanges), edit the
`JOINTS` dict — MediaPipe's 21-keypoint convention applies.

## Output schema (`<stem>_skeleton.json`)

```json
{
  "meta": { ... summary stats ... },
  "frames": [
    {
      "frame_idx": 150,
      "timestamp_ns": 1779822664...,
      "hands": [
        {
          "label": "Left",                                  ← MediaPipe anatomical label
          "score_L": 0.99, "score_R": 0.97,                 ← detection confidence per eye
          "keypoints_camera_m": [[X,Y,Z], ...×21],          ← LEFT-CAMERA FRAME, METERS
          "keypoints_wrist_m":  [[dX,dY,dZ], ...×21],       ← wrist-relative (kp - kp[0])
          "keypoints_pixel_L":  [[u,v], ...×21],            ← raw px on left  image (1280×720)
          "keypoints_pixel_R":  [[u,v], ...×21],            ← raw px on right image
          "wrist_camera_m": [X,Y,Z],                        ← convenience: kp[0]
          "reproj_err_px_L": [...×21],                      ← reprojection residual L (px)
          "reproj_err_px_R": [...×21]                       ← reprojection residual R (px)
        }
      ]
    }, ...
  ]
}
```

## Coordinate systems — read this carefully

### `keypoints_camera_m` (primary)

OpenCV convention, origin at **left camera optical center**:

```
   ●─────→  +X   (rightward, in physical space)
   │
   ↓
   +Y          (downward)

   ↗ +Z        (forward, into the scene)
```

Units: **meters**. Example: a hand 50 cm in front and 10 cm to the right
of the camera → `(0.10, 0.00, 0.50)`.

### `keypoints_wrist_m`

The same vectors with wrist subtracted: `kp[i] - kp[0]`. Useful for:
- Hand-shape classification (invariant to where the hand is in space)
- Finger-joint kinematics (each joint relative to the palm)

### `keypoints_pixel_L` / `keypoints_pixel_R`

Raw image-pixel coordinates on the 1280×720 left/right eye images. Useful for:
- Drawing overlays
- Manual inspection / debugging
- Disparity sanity check: same y for the same joint after rectification

### What we DO NOT have

- **World / room coordinate frame** — would need extra calibration (e.g., AprilTag on
  the wall) or ZED's positional tracking (which needs the SDK).
- **IMU sensor coordinate frame** — needs to be derived from world frame + hand
  pose, future work.

## Calibration parameters (for ZED 2i SN 38429607, HD720)

Loaded from `calib/SN38429607.conf`. Key values at HD720 (1280×720):

| Parameter | Left | Right |
|-----------|------|-------|
| fx        | 531.215 px | 532.915 px |
| fy        | 531.21 px  | 532.875 px |
| cx        | 639.905 px | 635.085 px |
| cy        | 366.479 px | 358.5615 px |
| k1/k2/k3  | -0.053 / 0.026 / -0.010 | -0.059 / 0.035 / -0.015 |

Stereo extrinsics:
- **Baseline**: 119.998 mm (≈ 12 cm)
- TY = -0.194 mm, TZ = 0.175 mm (sub-mm vertical/depth offsets)
- RX/CV/RZ ~ 0.001 rad (≈ 0.06°, negligible misalignment)

Disparity → depth example: for a point at 50 cm depth on the optical axis,
the horizontal disparity is `(fx * B / Z) = 531.21 × 0.12 / 0.5 ≈ 127 px`.

## Known limitations

1. **Detection rate ~57%** in our two pilot recordings — hands not always in
   frame, and triangulation requires the hand visible in **both** eyes. The
   left/right eye baseline overlap is fine, but if the hand goes out of one
   eye's field of view, that frame is dropped.

2. **Outlier residuals** (some frames show reprojection > 30 px max). Caused by
   MediaPipe occasionally putting a keypoint in the wrong spot in one eye.
   `process_svo.py` does NOT filter these currently — downstream consumers
   should reject frames with `max(reproj_err_px) > THRESHOLD` (suggest 5 px).

3. **MediaPipe handedness label is anatomical** (Left = subject's left hand
   from THEIR perspective, which appears on the RIGHT of the image because the
   camera mirrors).

4. **No temporal smoothing** between frames. Per-frame independent triangulation.
   If the paper uses these as virtual-IMU ground truth, consider a Kalman /
   spline smoother on `keypoints_wrist_m` before differentiating for velocity /
   acceleration.

5. **Resolution detection** uses `2*cx, 2*cy` from calibration, which gives
   (1280, 733) for HD720 because principal point isn't exactly centered. This
   is a metadata-only quirk; actual image processing uses 1280×720 from the
   decoded frame.

## Performance (Apple M5 Pro, MediaPipe via Metal)

- SVO2 frame decode: ~5 ms/frame
- MediaPipe Hands per eye: ~30 ms/frame
- Triangulation + bookkeeping: <1 ms/frame
- **End-to-end: ~14-16 fps** (real video is 30 fps, so this is 0.5× real-time)

For real-time at 30 fps, the two MediaPipe runs would need to be parallelized
(one per process / thread). Out of scope for this offline pipeline.

## Reproducing the calibration fetch

If we ever get a new ZED 2i (different serial), grab its calibration by:

```bash
curl -sSL "https://www.stereolabs.com/developers/calib/?SN=<NEW_SN>" \
    -o calib/SN<NEW_SN>.conf
```

Then point `--calib` to the new file.

## Dependencies (pinned in venv; reproducible)

- Python 3.12 (mediapipe doesn't yet support 3.13/3.14)
- mcap 1.3.1
- mediapipe 0.10.21
- opencv-python 4.11.0
- av 17.0.1 (currently unused but kept for future H.264 fallback)
- numpy 1.26.4
- matplotlib (for trajectory plots)
