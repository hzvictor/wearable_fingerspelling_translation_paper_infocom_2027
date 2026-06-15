"""ZED 2i factory calibration loader.

The .conf file is fetched from Stereolabs' public calibration server:
    https://www.stereolabs.com/developers/calib/?SN=<serial>

It contains per-resolution intrinsics, distortion, and the stereo extrinsics
between the two cameras.

This module exposes a single class `StereoCalib` that holds:
    K_L, K_R       : (3,3) intrinsic matrices (pixels)
    dist_L, dist_R : (5,) distortion (k1, k2, p1, p2, k3) — OpenCV order
    R_LR           : (3,3) rotation of right-cam frame w.r.t. left-cam frame
    T_LR           : (3,)  translation of right-cam origin in left-cam frame, in meters

Convention follows OpenCV stereo: a 3D point X_L in left-cam coords maps to
right-cam coords as X_R = R_LR.T @ (X_L - T_LR). This matches what cv2.stereoRectify
expects when called as stereoRectify(K_L, dist_L, K_R, dist_R, size, R, T) with
R = R_LR.T and T = -R_LR.T @ T_LR (i.e., the transform from left to right cam).

Coordinate axes (OpenCV convention):
    +X right, +Y down, +Z forward
"""
from __future__ import annotations
import configparser
from dataclasses import dataclass
from pathlib import Path
import numpy as np


# Map our resolution name to the section suffix used in the .conf file
RESOLUTION_KEY = {
    "VGA":   "VGA",
    "HD":    "HD",     # 1280 x 720
    "HD720": "HD",
    "FHD":   "FHD",    # 1920 x 1080
    "2K":    "2K",     # 2208 x 1242
}


@dataclass
class StereoCalib:
    K_L: np.ndarray         # (3, 3)
    K_R: np.ndarray         # (3, 3)
    dist_L: np.ndarray      # (5,)  -- (k1, k2, p1, p2, k3)
    dist_R: np.ndarray      # (5,)
    R_LR: np.ndarray        # (3, 3)
    T_LR: np.ndarray        # (3,) meters
    baseline_m: float
    resolution: tuple[int, int]  # (W, H)
    source_path: Path

    # --- Convenience projection matrices for cv2.triangulatePoints ---
    @property
    def P_L(self) -> np.ndarray:
        """Left projection: K_L @ [I | 0]. Operates on UNDISTORTED points."""
        return self.K_L @ np.hstack([np.eye(3), np.zeros((3, 1))])

    @property
    def P_R(self) -> np.ndarray:
        """Right projection in the left-camera world frame.

        World := left-cam frame. Right cam pose in world is (R_LR, T_LR).
        For a world point X, its right-cam coords are X_R = R_LR.T (X - T_LR).
        Projection: P_R = K_R [R_LR.T | -R_LR.T @ T_LR].
        """
        R_wr_to_rc = self.R_LR.T
        t = -R_wr_to_rc @ self.T_LR.reshape(3, 1)
        return self.K_R @ np.hstack([R_wr_to_rc, t])

    def rectify(self, image_size: tuple[int, int] | None = None):
        """Compute stereo-rectification maps and the rectified projection
        matrices. Returns (mapL1, mapL2, mapR1, mapR2, P1_rect, P2_rect, Q).

        After remap-ing both eyes with these maps, rows are aligned and disparity
        works directly. cv2.triangulatePoints with (P1_rect, P2_rect) on the
        rectified pixel coords yields 3D points in the rectified frame (which is
        a small rotation away from the original left-camera frame -- we ignore
        that residual rotation as it's < 0.1deg for ZED 2i).
        """
        import cv2  # lazy import
        w, h = image_size if image_size else self.resolution
        R_to_right = self.R_LR.T  # left -> right
        T_to_right = (-R_to_right @ self.T_LR).reshape(3, 1)

        R1, R2, P1, P2, Q, *_ = cv2.stereoRectify(
            self.K_L, self.dist_L,
            self.K_R, self.dist_R,
            (w, h),
            R_to_right, T_to_right,
            flags=cv2.CALIB_ZERO_DISPARITY,
            alpha=0.0,
        )
        mapL1, mapL2 = cv2.initUndistortRectifyMap(
            self.K_L, self.dist_L, R1, P1, (w, h), cv2.CV_32FC1
        )
        mapR1, mapR2 = cv2.initUndistortRectifyMap(
            self.K_R, self.dist_R, R2, P2, (w, h), cv2.CV_32FC1
        )
        return mapL1, mapL2, mapR1, mapR2, P1, P2, Q


def _eul_xyz_to_rot(rx: float, ry: float, rz: float) -> np.ndarray:
    """ZED .conf gives RX (around X), CV (around Y -- "convergence"), RZ (around Z).
    Apply in order Z * Y * X (standard for small Euler corrections)."""
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def load_calib(conf_path: str | Path, resolution: str = "HD") -> StereoCalib:
    """Read the .conf and produce a StereoCalib for the requested resolution."""
    conf_path = Path(conf_path)
    cp = configparser.ConfigParser()
    cp.read(conf_path)

    res_key = RESOLUTION_KEY[resolution.upper()]
    sec_L = f"LEFT_CAM_{res_key}"
    sec_R = f"RIGHT_CAM_{res_key}"
    sec_S = "STEREO"

    def K_from(section: str) -> np.ndarray:
        fx = cp.getfloat(section, "fx")
        fy = cp.getfloat(section, "fy")
        cx = cp.getfloat(section, "cx")
        cy = cp.getfloat(section, "cy")
        return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float64)

    def dist_from(section: str) -> np.ndarray:
        # OpenCV order: k1, k2, p1, p2, k3
        return np.array([
            cp.getfloat(section, "k1"),
            cp.getfloat(section, "k2"),
            cp.getfloat(section, "p1"),
            cp.getfloat(section, "p2"),
            cp.getfloat(section, "k3"),
        ], dtype=np.float64)

    K_L = K_from(sec_L)
    K_R = K_from(sec_R)
    dist_L = dist_from(sec_L)
    dist_R = dist_from(sec_R)

    # Image size for this resolution (cx, cy ~= image_center)
    # We infer width = 2*cx, height = 2*cy. Works for the standard ZED resolutions
    # because principal point is near image center.
    w = int(round(2 * cp.getfloat(sec_L, "cx")))
    h = int(round(2 * cp.getfloat(sec_L, "cy")))

    baseline_mm = cp.getfloat(sec_S, "Baseline")
    ty_mm = cp.getfloat(sec_S, "TY")
    tz_mm = cp.getfloat(sec_S, "TZ")

    # ZED .conf says T_LR.x = Baseline (positive). Right camera is to the right
    # of left camera, so in left-cam OpenCV frame (+X = right), the right cam
    # origin sits at (+Baseline, TY, TZ). T in meters.
    T_LR = np.array([baseline_mm, ty_mm, tz_mm], dtype=np.float64) / 1000.0

    # Per-resolution Euler corrections (radians). The resolution-keyed entries
    # all carry the same value in factory ZED 2i calibrations, but we read the
    # specific one for safety.
    rx = cp.getfloat(sec_S, f"RX_{res_key}", fallback=0.0)
    ry = cp.getfloat(sec_S, f"CV_{res_key}", fallback=0.0)  # convergence
    rz = cp.getfloat(sec_S, f"RZ_{res_key}", fallback=0.0)
    R_LR = _eul_xyz_to_rot(rx, ry, rz)

    return StereoCalib(
        K_L=K_L, K_R=K_R, dist_L=dist_L, dist_R=dist_R,
        R_LR=R_LR, T_LR=T_LR,
        baseline_m=baseline_mm / 1000.0,
        resolution=(w, h),
        source_path=conf_path,
    )
