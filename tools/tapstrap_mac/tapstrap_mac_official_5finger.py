"""
TapStrap 5-finger raw collector on macOS — OFFICIAL tap-python-sdk + 2 minimal patches.

Two surgical patches over the stock official SDK; nothing else changes:

  PATCH 1 (connection): the official posix backend finds the device only via
      retrieveConnectedPeripheralsWithServices_(), which returns nothing when the
      Tap is bonded as an HID keyboard. We replace JUST that step with a
      BleakScanner scan + bleak connect (with retry for the one-time pairing).

  PATCH 2 (parser): on this Mac the negotiated MTU is 23 -> 20-byte notifications,
      while a full accelerometer frame is 34 bytes (4-byte header + 30-byte
      payload = 5 fingers x 3 axes). The official parsers.raw_data_msg decodes
      each 20-byte notification independently and therefore drops the trailing
      fingers (yields only thumb/index/middle = 3 fingers, ~55 Hz). We replace
      that ONE function with a stateful reassembler that buffers the NUS byte
      stream across notifications and rebuilds whole frames -> all 5 fingers,
      ~200 Hz.

Everything else (set_input_mode raw, 10s auto-refresh, register_raw_data_events,
the message-dict format) is stock official SDK.

Run:
    source .venv/bin/activate
    python3 tapstrap_mac_official_5finger.py [duration_seconds]
"""

try:
    import CoreBluetooth  # noqa: F401  (precede bleak import on Apple Silicon)
except Exception:
    pass

import asyncio
import csv
import struct
import sys
import time
from pathlib import Path

from bleak import BleakScanner
from tapsdk import TapSDK, TapInputMode
from tapsdk import parsers

FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
HEADER = 4
MSG_TYPE_BIT = 1 << 31
ACCEL_SAMPLES, ACCEL_PAYLOAD = 15, 30
IMU_SAMPLES, IMU_PAYLOAD = 6, 12


# ---------------------------------------------------------------------------------
# PATCH 2: stateful reassembling replacement for parsers.raw_data_msg.
# Returns the same list-of-dicts format the official on_raw_data expects:
#   {"type": "accl"|"imu", "ts": int, "payload": [int,...]}
# ---------------------------------------------------------------------------------
class _Reassembler:
    msg_type_value = MSG_TYPE_BIT  # keep the attribute the official code references

    def __init__(self):
        self.buf = bytearray()

    def __call__(self, data):
        self.buf += bytes(data)
        out = []
        while len(self.buf) >= HEADER:
            meta = struct.unpack_from("<I", self.buf, 0)[0]
            if meta == 0:
                del self.buf[0:1]      # zero padding -> resync by 1 byte
                continue
            if meta & MSG_TYPE_BIT:
                n, plen, kind, ts = ACCEL_SAMPLES, ACCEL_PAYLOAD, "accl", meta & (MSG_TYPE_BIT - 1)
            else:
                n, plen, kind, ts = IMU_SAMPLES, IMU_PAYLOAD, "imu", meta
            if len(self.buf) < HEADER + plen:
                break                  # frame split across notifications -> wait
            payload = list(struct.unpack_from("<%dh" % n, self.buf, HEADER))
            del self.buf[0:HEADER + plen]
            out.append({"type": kind, "ts": ts, "payload": payload})
        return out


parsers.raw_data_msg = _Reassembler()    # install the fix into the official SDK

ACCEL = []


def on_raw_data(identifier, packets):
    for m in packets:
        if m["type"] == "accl" and len(m["payload"]) >= 15:
            ACCEL.append((m["ts"], m["payload"][:15]))


def fingers_with_data(p):
    return [FINGERS[i] for i in range(5) if any(p[i * 3:i * 3 + 3])]


async def connect_official_with_scan(loop):
    """PATCH 1: scan + connect (with retry), then hand control to the official SDK."""
    dev = None
    for scan_try in range(1, 7):       # ~30s total: keep looking while you free the device
        print(f"[scan] scanning for advertising Tap (try {scan_try}/6) ...")
        dev = await BleakScanner.find_device_by_filter(
            lambda d, ad: (d.name or "").lower().startswith("tap"), timeout=5.0)
        if dev:
            break
        print("       not found. If Tap shows 'Connected' (keyboard) in macOS "
              "Bluetooth, Disconnect/Forget it so it advertises.")
    if not dev:
        print("[err] Tap never advertised. In macOS Bluetooth, Forget the Tap "
              "(it keeps auto-connecting as a keyboard), then rerun.", file=sys.stderr)
        return None
    print(f"[scan] found {dev.name} ({dev.address})")
    last_err = None
    for attempt in range(1, 6):
        tap = TapSDK(loop=loop, address=dev.address)
        try:
            await tap.client.connect()
            await tap.client.get_services()
            print(f"[conn] connected={tap.client.is_connected} "
                  f"mtu={getattr(tap.client,'mtu_size','?')} (attempt {attempt})")
            return tap
        except Exception as e:
            last_err = e
            print(f"[conn] attempt {attempt} failed: {e} -> retry in 2s "
                  f"(click Connect if a pairing dialog appears)")
            try:
                await tap.client.disconnect()
            except Exception:
                pass
            await asyncio.sleep(2)
    print(f"[err] no stable connection: {last_err}", file=sys.stderr)
    return None


async def run(loop, duration):
    tap = await connect_official_with_scan(loop)
    if not tap:
        return
    await tap.register_raw_data_events(on_raw_data)             # official
    await tap.set_input_mode(TapInputMode("raw", sensitivity=[0, 0, 0]))  # official
    print(f"[mode] raw mode set (reassembling parser). Fingerspell ~{duration}s ...\n")

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

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "tap_raw_accel_5finger.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_ms"] + [f"{fg}_{ax}" for fg in FINGERS for ax in "xyz"])
        for ts, p in ACCEL:
            w.writerow([ts] + p)
    ever = set()
    for _, p in ACCEL:
        ever.update(fingers_with_data(p))
    rate = len(ACCEL) / max(1e-9, time.time() - t0)
    print("\n" + "=" * 70)
    print(f"RESULT: frames={len(ACCEL)} (~{rate:.0f} Hz)  "
          f"fingers seen={sorted(ever, key=FINGERS.index)}")
    print("VERDICT: ✅ all 5 fingers on Mac" if len(ever) >= 5
          else f"VERDICT: still {len(ever)} fingers — check finger motion / device state")
    print(f"data -> {out}")
    print("=" * 70)

    # clean shutdown: stop the stream and let late notifications drain before the
    # event loop closes (avoids the harmless 'Event loop is closed' traceback)
    try:
        await tap.set_input_mode(TapInputMode("text"))
        await tap.client.disconnect()
        await asyncio.sleep(0.3)
    except Exception:
        pass


if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run(loop, dur))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
