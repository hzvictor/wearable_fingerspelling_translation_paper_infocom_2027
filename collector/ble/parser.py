"""Raw Tap Strap sensor packet parser — ported from collect_gestures.py:parse_raw.

A single BLE notification (182 bytes when Developer Mode is on, MTU 185) packs
several frames back-to-back, each: 4-byte little-endian timestamp header + N
int16 channels. The timestamp's high bit (RAW_MSG_TYPE_BIT) distinguishes an
accelerometer frame (15 channels, 5 fingers x XYZ) from an IMU frame (6
channels). Trailing zero padding ends the loop.
"""
from .constants import RAW_MSG_TYPE_BIT, ACCL_CHANNELS_FULL, IMU_CHANNELS


def parse_raw(data: bytes) -> list[dict]:
    """Parse one raw-sensor notification into a list of frame dicts.

    Each frame: {"type": "accl"|"imu", "ts": int, "payload": list[int]}.
    The caller stamps "recv_time" (wall-clock seconds) on each frame.
    """
    messages = []
    ptr = 0
    n_bytes = len(data)
    while ptr < n_bytes:
        if ptr + 4 > n_bytes:
            break
        ts = int.from_bytes(data[ptr:ptr + 4], "little", signed=False)
        if ts == 0:
            break  # zero padding => end of frames in this notification
        ptr += 4
        if ts > RAW_MSG_TYPE_BIT:
            msg_type = "accl"
            ts -= RAW_MSG_TYPE_BIT
            n = ACCL_CHANNELS_FULL   # 15 with Developer Mode; truncates gracefully if fewer bytes
        else:
            msg_type = "imu"
            n = IMU_CHANNELS
        payload = []
        for _ in range(n):
            if ptr + 2 <= n_bytes:
                payload.append(int.from_bytes(data[ptr:ptr + 2], "little", signed=True))
            ptr += 2
        messages.append({"type": msg_type, "ts": ts, "payload": payload})
    return messages
