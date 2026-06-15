"""Stereo MediaPipe Hands: run on both eyes, match hands by handedness, triangulate.

Pipeline per frame:
    1. Detect 21 keypoints on left eye and right eye (independently).
    2. Match hands across eyes by MediaPipe's "Left"/"Right" handedness label.
    3. Undistort the 21 keypoints in each eye using the camera's distortion model.
    4. cv2.triangulatePoints(P_L, P_R, undistorted_L, undistorted_R)
       -> 4D homogeneous -> divide -> (X, Y, Z) in left-camera frame, meters.
    5. Compute reprojection residuals (px) as a quality signal.

We use the UNRECTIFIED projection matrices P_L = K_L [I|0] and P_R = K_R [R|t]
with undistorted keypoints. Stereo rectification is unnecessary here because we
already have explicit 2D-2D correspondences from MediaPipe -- rectification is
only needed when doing dense block matching that searches along epipolar lines.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
import cv2

import mediapipe as mp

from .calibration import StereoCalib

_mp_hands = mp.solutions.hands

# MediaPipe joint 0 is the wrist.
WRIST_IDX = 0
# Some useful named joints
FINGERTIPS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}


@dataclass
class HandObservation3D:
    label: str                      # "Left" or "Right" (MediaPipe anatomical convention)
    score_L: float
    score_R: float
    kp_pixel_L: np.ndarray          # (21, 2) raw pixel coords on left eye
    kp_pixel_R: np.ndarray          # (21, 2) raw pixel coords on right eye
    kp_camera_m: np.ndarray         # (21, 3) 3D in LEFT-camera frame, meters
    kp_wrist_m: np.ndarray          # (21, 3) wrist-relative (kp_camera - wrist), meters
    wrist_camera_m: np.ndarray      # (3,)
    reproj_err_px_L: np.ndarray     # (21,) reprojection residual on left eye
    reproj_err_px_R: np.ndarray     # (21,) on right eye


def _undistort(kp_px: np.ndarray, K: np.ndarray, dist: np.ndarray) -> np.ndarray:
    """Remove lens distortion from (N, 2) pixel keypoints. Returns (N, 2) pixel coords
    that are valid under a pure pin-hole K (no distortion)."""
    pts = kp_px.reshape(-1, 1, 2).astype(np.float64)
    und = cv2.undistortPoints(pts, K, dist, P=K)
    return und.reshape(-1, 2)


def _triangulate(P_L: np.ndarray, P_R: np.ndarray,
                 kp_L_undist: np.ndarray, kp_R_undist: np.ndarray) -> np.ndarray:
    """cv2.triangulatePoints wrapper. Inputs (N,2), output (N,3) in P_L's world frame."""
    pts_L = kp_L_undist.T.astype(np.float64)   # (2, N)
    pts_R = kp_R_undist.T.astype(np.float64)
    X_h = cv2.triangulatePoints(P_L, P_R, pts_L, pts_R)  # (4, N)
    X = (X_h[:3] / X_h[3:]).T                            # (N, 3)
    return X


def _reproject(P: np.ndarray, X_world: np.ndarray) -> np.ndarray:
    """Project (N,3) world points through (3,4) P to (N,2) pixels."""
    Xh = np.hstack([X_world, np.ones((X_world.shape[0], 1))])  # (N,4)
    xh = (P @ Xh.T).T   # (N,3)
    return xh[:, :2] / xh[:, 2:3]


class StereoHandTracker:
    """One instance handles a video session: keep MediaPipe state across frames
    for temporal smoothing. Two MediaPipe runners (one per eye)."""

    def __init__(self, calib: StereoCalib,
                 max_hands: int = 2,
                 detect_conf: float = 0.5,
                 track_conf: float = 0.5):
        self.calib = calib
        self.hands_L = _mp_hands.Hands(
            static_image_mode=False, max_num_hands=max_hands,
            min_detection_confidence=detect_conf,
            min_tracking_confidence=track_conf,
        )
        self.hands_R = _mp_hands.Hands(
            static_image_mode=False, max_num_hands=max_hands,
            min_detection_confidence=detect_conf,
            min_tracking_confidence=track_conf,
        )
        self.P_L = calib.P_L
        self.P_R = calib.P_R

    def close(self):
        self.hands_L.close()
        self.hands_R.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @staticmethod
    def _extract_hands(result, img_w: int, img_h: int) -> dict[str, dict]:
        """Return {label: {"px": (21,2), "score": float}} keyed by 'Left'/'Right'."""
        out = {}
        if not result.multi_hand_landmarks:
            return out
        for lms, handed in zip(result.multi_hand_landmarks, result.multi_handedness):
            label = handed.classification[0].label
            score = float(handed.classification[0].score)
            px = np.array([(lm.x * img_w, lm.y * img_h) for lm in lms.landmark],
                          dtype=np.float64)
            # If label collision, keep higher-score one
            if label in out and out[label]["score"] >= score:
                continue
            out[label] = {"px": px, "score": score}
        return out

    def process_frame(self, left_bgr: np.ndarray, right_bgr: np.ndarray) -> list[HandObservation3D]:
        """Detect hands on both eyes, match by handedness, triangulate.
        Returns one HandObservation3D per hand that was visible in BOTH eyes."""
        h, w = left_bgr.shape[:2]
        rgb_L = cv2.cvtColor(left_bgr, cv2.COLOR_BGR2RGB)
        rgb_R = cv2.cvtColor(right_bgr, cv2.COLOR_BGR2RGB)
        res_L = self.hands_L.process(rgb_L)
        res_R = self.hands_R.process(rgb_R)
        hands_L = self._extract_hands(res_L, w, h)
        hands_R = self._extract_hands(res_R, w, h)

        observations = []
        for label in set(hands_L) & set(hands_R):
            kp_L = hands_L[label]["px"]
            kp_R = hands_R[label]["px"]
            sL = hands_L[label]["score"]
            sR = hands_R[label]["score"]

            kp_L_u = _undistort(kp_L, self.calib.K_L, self.calib.dist_L)
            kp_R_u = _undistort(kp_R, self.calib.K_R, self.calib.dist_R)

            X_cam = _triangulate(self.P_L, self.P_R, kp_L_u, kp_R_u)  # (21, 3) meters

            # Reprojection residuals: against the *undistorted* coords (apples-to-apples
            # for the pin-hole projection)
            reproj_L = _reproject(self.P_L, X_cam)
            reproj_R = _reproject(self.P_R, X_cam)
            err_L = np.linalg.norm(reproj_L - kp_L_u, axis=1)
            err_R = np.linalg.norm(reproj_R - kp_R_u, axis=1)

            wrist = X_cam[WRIST_IDX]
            kp_wrist = X_cam - wrist

            observations.append(HandObservation3D(
                label=label,
                score_L=sL,
                score_R=sR,
                kp_pixel_L=kp_L,
                kp_pixel_R=kp_R,
                kp_camera_m=X_cam,
                kp_wrist_m=kp_wrist,
                wrist_camera_m=wrist,
                reproj_err_px_L=err_L,
                reproj_err_px_R=err_R,
            ))
        return observations
