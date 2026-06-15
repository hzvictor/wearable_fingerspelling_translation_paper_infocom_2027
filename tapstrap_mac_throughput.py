"""
TapStrap throughput experiment on macOS with MODERN bleak (3.x), pure-bleak (no tapsdk).

Question: can we beat the ~23 Hz / 20-byte-notification ceiling seen with bleak
0.12.1?  We connect, report the REAL negotiated MTU, then in raw mode measure:
  - actual BLE notification length distribution (is it still 20B, or larger?)
  - notification rate (notifs/s)  -> the true link throughput
  - complete accelerometer-frame rate (Hz) after reassembly
  - fingers with data

If notifications grow past 20B, throughput (and Hz) scales up accordingly.

Run:
    ./.venv2/bin/python tapstrap_mac_throughput.py [duration_seconds]
"""

import asyncio
import struct
import sys
import time
from collections import Counter

from bleak import BleakScanner, BleakClient

NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # write: set mode
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # notify: raw stream
RAW_MODE_CMD = bytes([0x03, 0x0C, 0x00, 0x0A, 0x00, 0x00, 0x00])

FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
HEADER = 4
MSG_TYPE_BIT = 1 << 31
ACCEL_N, ACCEL_PL = 15, 30
IMU_N, IMU_PL = 6, 12

STATE = {
    "buf": bytearray(),
    "notif_lens": Counter(),
    "notif_count": 0,
    "accel": [],   # (ts, [15])
    "imu": 0,
}


def reassemble(data):
    STATE["notif_count"] += 1
    STATE["notif_lens"][len(data)] += 1
    buf = STATE["buf"]
    buf += bytes(data)
    while len(buf) >= HEADER:
        meta = struct.unpack_from("<I", buf, 0)[0]
        if meta == 0:
            del buf[0:1]
            continue
        if meta & MSG_TYPE_BIT:
            n, pl, kind, ts = ACCEL_N, ACCEL_PL, "accl", meta & (MSG_TYPE_BIT - 1)
        else:
            n, pl, kind, ts = IMU_N, IMU_PL, "imu", meta
        if len(buf) < HEADER + pl:
            break
        payload = list(struct.unpack_from("<%dh" % n, buf, HEADER))
        del buf[0:HEADER + pl]
        if kind == "accl":
            STATE["accel"].append((ts, payload))
        else:
            STATE["imu"] += 1


def on_notify(_char, data):
    reassemble(data)


def fingers_with_data(p):
    return [FINGERS[i] for i in range(5) if any(p[i * 3:i * 3 + 3])]


async def main(duration):
    print("[scan] looking for advertising Tap ...")
    dev = await BleakScanner.find_device_by_filter(
        lambda d, ad: (d.name or "").lower().startswith("tap"), timeout=20.0)
    if not dev:
        print("[err] Tap not advertising. Forget/Disconnect it in macOS Bluetooth first.")
        return
    print(f"[scan] found {dev.name} ({dev.address})")

    async with BleakClient(dev) as c:
        print(f"[conn] connected={c.is_connected}  REAL mtu={c.mtu_size}  "
              f"(notif payload up to {c.mtu_size - 3}B; full accel frame = 34B)")
        await c.start_notify(NUS_TX, on_notify)
        await c.write_gatt_char(NUS_RX, RAW_MODE_CMD, response=False)
        print(f"[mode] raw mode set. Streaming {duration}s ...\n")

        t0 = time.time()
        last_notif = 0
        last_accel = 0
        while time.time() - t0 < duration:
            await asyncio.sleep(3)
            await c.write_gatt_char(NUS_RX, RAW_MODE_CMD, response=False)  # refresh
            nc = STATE["notif_count"]
            na = len(STATE["accel"])
            nrate = (nc - last_notif) / 3.0
            arate = (na - last_accel) / 3.0
            last_notif, last_accel = nc, na
            cover = fingers_with_data(STATE["accel"][-1][1]) if STATE["accel"] else []
            print(f"[t={time.time()-t0:4.0f}s] notif {nc:6d} (~{nrate:.0f}/s) | "
                  f"accel {na:6d} (~{arate:.0f} Hz) | fingers: {cover}")

    el = time.time() - t0
    na = len(STATE["accel"])
    ever = set()
    for _, p in STATE["accel"]:
        ever.update(fingers_with_data(p))
    print("\n" + "=" * 72)
    print(f"REAL MTU was {c.mtu_size}")
    print(f"notification sizes seen: {dict(STATE['notif_lens'])}")
    print(f"notifications: {STATE['notif_count']} (~{STATE['notif_count']/el:.0f}/s)")
    print(f"accel frames : {na} (~{na/el:.0f} Hz)   imu frames: {STATE['imu']} (~{STATE['imu']/el:.0f} Hz)")
    print(f"fingers seen : {sorted(ever, key=FINGERS.index)}")
    print("=" * 72)


if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    asyncio.run(main(dur))
