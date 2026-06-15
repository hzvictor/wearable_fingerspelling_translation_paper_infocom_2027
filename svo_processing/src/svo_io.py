"""ZED SVO2 reader (Mac-friendly, no ZED SDK required).

A SVO2 file is an MCAP container with these channels:
    svo_header                              JSON, one-shot metadata + calibration JSON
    svo_footer                              JSON, one-shot
    Camera_SN<SN>/side_by_side              "zed_sdk_encoded" video, one msg per frame
    Camera_SN<SN>/sensors                   JSON IMU samples (~400 Hz)
    Camera_SN<SN>/integrated_sensors        JSON synced-with-video sensors

The "side_by_side" payload is a custom container of 4 JPEGs, each decoding to a
5120 x 180 grayscale strip. Stacking them vertically yields a 5120 x 720 buffer
that is YUYV (YUV 4:2:2) packed at 2560 px wide. Converting YUYV -> BGR then
splitting the left & right halves gives the two 1280 x 720 RGB eye images.

This module exposes:
    SvoReader(path)
        .header_json: dict             (calibration JSON from svo_header)
        .iter_frames(): yields (frame_idx, log_time_ns, left_bgr, right_bgr)
        .iter_imu():    yields dict per imu sample
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import numpy as np
import cv2
from mcap.reader import make_reader


def _decode_zed_sdk_encoded(data: bytes) -> np.ndarray:
    """Decode one side_by_side payload -> 720 x 2560 x 3 BGR image."""
    soi = []
    i = 0
    while True:
        i = data.find(b"\xff\xd8\xff", i)
        if i < 0:
            break
        soi.append(i)
        i += 1
    if len(soi) != 4:
        raise ValueError(f"expected 4 JPEGs, got {len(soi)}")

    strips = []
    for k, start in enumerate(soi):
        end = soi[k + 1] if k + 1 < len(soi) else len(data)
        jpg = data[start:end]
        last_eoi = jpg.rfind(b"\xff\xd9")
        if last_eoi > 0:
            jpg = jpg[: last_eoi + 2]
        img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if img is None or img.shape != (180, 5120):
            raise ValueError(f"strip {k} bad: shape={None if img is None else img.shape}")
        strips.append(img)

    stacked = np.vstack(strips)               # 720 x 5120
    yuyv = stacked.reshape(720, 2560, 2).astype(np.uint8)
    return cv2.cvtColor(yuyv, cv2.COLOR_YUV2BGR_YUYV)  # 720 x 2560 x 3


def split_lr(bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    w = bgr.shape[1] // 2
    return bgr[:, :w], bgr[:, w:]


@dataclass
class SvoReader:
    path: Path
    video_topic: str = ""   # auto-detected
    imu_topic: str = ""     # auto-detected
    integrated_topic: str = ""
    header_json: dict = None

    def __post_init__(self):
        self.path = Path(self.path)
        # Detect channel names by scanning summary
        with open(self.path, "rb") as f:
            reader = make_reader(f)
            summary = reader.get_summary()
            for ch in summary.channels.values():
                t = ch.topic
                if t.endswith("/side_by_side"):
                    self.video_topic = t
                elif t.endswith("/sensors") and not t.endswith("/integrated_sensors"):
                    self.imu_topic = t
                elif t.endswith("/integrated_sensors"):
                    self.integrated_topic = t

            for sch, ch, msg in reader.iter_messages(topics=["svo_header"]):
                try:
                    self.header_json = json.loads(msg.data.decode("utf-8", "replace"))
                except Exception:
                    self.header_json = {}
                break

        if not self.video_topic:
            raise RuntimeError(f"No side_by_side video topic in {self.path}")

    def iter_frames(self) -> Iterator[tuple[int, int, np.ndarray, np.ndarray]]:
        """Yield (frame_idx, log_time_ns, left_bgr, right_bgr)."""
        idx = 0
        with open(self.path, "rb") as f:
            reader = make_reader(f)
            for sch, ch, msg in reader.iter_messages(topics=[self.video_topic]):
                bgr = _decode_zed_sdk_encoded(msg.data)
                left, right = split_lr(bgr)
                yield idx, int(msg.log_time), left, right
                idx += 1

    def iter_imu(self) -> Iterator[dict]:
        """Yield IMU samples as decoded JSON dicts (raw schema from ZED)."""
        if not self.imu_topic:
            return
        with open(self.path, "rb") as f:
            reader = make_reader(f)
            for sch, ch, msg in reader.iter_messages(topics=[self.imu_topic]):
                try:
                    sample = json.loads(msg.data.decode("utf-8", "replace"))
                except Exception:
                    continue
                sample["_log_time_ns"] = int(msg.log_time)
                yield sample

    def summary(self) -> dict:
        """Quick metadata: frame count, duration, IMU count."""
        with open(self.path, "rb") as f:
            reader = make_reader(f)
            s = reader.get_summary().statistics
        per_topic = dict(s.channel_message_counts) if s else {}
        # Map channel id -> topic via re-open (cheap)
        return {
            "path": str(self.path),
            "total_messages": s.message_count if s else 0,
            "duration_s": (s.message_end_time - s.message_start_time) / 1e9 if s else 0.0,
            "start_ns": s.message_start_time if s else 0,
            "end_ns": s.message_end_time if s else 0,
            "video_topic": self.video_topic,
            "imu_topic": self.imu_topic,
        }
