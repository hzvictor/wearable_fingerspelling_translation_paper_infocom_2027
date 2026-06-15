"""
TapStrap raw-sensor collector on macOS — OFFICIAL SDK + cross-notification reassembly.

Use this ONLY if tapstrap_mac_test.py reported "only N<5 fingers" (MTU-truncated
notifications). It reuses the official tap-python-sdk for everything (scan,
connect, set raw mode, 10s auto-refresh) and ONLY replaces the buggy per-packet
parser with a stateful reassembler that buffers the NUS byte stream across
notifications, so a 34-byte accel frame split over several ~20-byte packets is
rebuilt and all 5 fingers are recovered.

How the swap stays "official": the posix backend calls `parsers.raw_data_msg(data)`
once per BLE notification. We replace that single function with a buffering
version; nothing else in the SDK changes.

Run
---
    source .venv/bin/activate
    python3 tapstrap_mac_collect_reassembled.py [duration_seconds]
"""

try:
    import CoreBluetooth  # noqa: F401  (must precede bleak import on Apple Silicon)
except Exception:
    pass

import asyncio
import csv
import struct
import sys
import time

from tapsdk import TapSDK, TapInputMode
from tapsdk import parsers

FINGERS = ["thumb", "index", "middle", "ring", "pinky"]

# Frame format (from tapsdk/parsers.py):
#   [4-byte header LE uint32][payload]
#     header MSB (bit31) = type: 1=accel(30B/15xint16), 0=imu(12B/6xint16)
#     header low 31 bits = timestamp(ms)
HEADER = 4
MSG_TYPE_BIT = 1 << 31
ACCEL_SAMPLES, ACCEL_PAYLOAD = 15, 30
IMU_SAMPLES, IMU_PAYLOAD = 6, 12


class _Reassembler:
    """Stateful replacement for parsers.raw_data_msg: buffers across notifications."""

    def __init__(self):
        self.buf = bytearray()

    def __call__(self, data):
        self.buf += bytes(data)
        out = []
        while True:
            if len(self.buf) < HEADER:
                break
            meta = struct.unpack_from("<I", self.buf, 0)[0]
            if meta == 0:
                # zero padding/keep-alive: drop one byte and resync
                del self.buf[0:1]
                continue
            if meta & MSG_TYPE_BIT:
                n, plen, kind, ts = ACCEL_SAMPLES, ACCEL_PAYLOAD, "accl", meta & (MSG_TYPE_BIT - 1)
            else:
                n, plen, kind, ts = IMU_SAMPLES, IMU_PAYLOAD, "imu", meta
            if len(self.buf) < HEADER + plen:
                break  # incomplete frame — wait for the next notification (the fix)
            payload = list(struct.unpack_from("<%dh" % n, self.buf, HEADER))
            del self.buf[0:HEADER + plen]
            out.append({"type": kind, "ts": ts, "payload": payload})
        return out


# Install the reassembling parser into the official SDK.
parsers.raw_data_msg = _Reassembler()

ACCEL = []


def on_raw_data(identifier, packets):
    for m in packets:
        if m["type"] == "accl" and len(m["payload"]) >= 15:
            ACCEL.append((m["ts"], m["payload"][:15]))


def fingers_with_data(p):
    return [FINGERS[i] for i in range(5) if any(p[i * 3:i * 3 + 3])]


async def run(loop, duration):
    tap = TapSDK(loop=loop)
    await tap.run()
    if not tap.client.is_connected:
        print("[err] not connected (pair + Developer Mode).", file=sys.stderr)
        return
    print(f"[conn] connected: {tap.client.is_connected}")
    await tap.register_raw_data_events(on_raw_data)
    await tap.set_input_mode(TapInputMode("raw", sensitivity=[0, 0, 0]))
    print(f"[mode] raw mode (reassembling). Fingerspell for ~{duration}s ...\n")

    t0 = time.time()
    last = 0
    while time.time() - t0 < duration:
        await asyncio.sleep(3)
        n = len(ACCEL)
        hz = (n - last) / 3.0
        last = n
        if n:
            print(f"[t={time.time()-t0:4.0f}s] accel {n:6d} (~{hz:.0f} Hz) | "
                  f"fingers w/ data: {fingers_with_data(ACCEL[-1][1])}")

    out = "tap_raw_accel.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_ms"] + [f"{fg}_{ax}" for fg in FINGERS for ax in "xyz"])
        for ts, p in ACCEL:
            w.writerow([ts] + p)
    ever = set()
    for _, p in ACCEL:
        ever.update(fingers_with_data(p))
    print(f"\n[done] {len(ACCEL)} frames, fingers seen={sorted(ever, key=FINGERS.index)} -> {out}")


if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    loop = asyncio.new_event_loop()       # Python 3.10+/3.14: no implicit current loop
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run(loop, dur))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
