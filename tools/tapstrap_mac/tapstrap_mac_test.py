"""
TapStrap raw-sensor test on macOS — using the OFFICIAL tap-python-sdk.

Goal of this script
-------------------
Decisively answer: "On this Mac, does the official SDK deliver all 5 fingers,
or only ~3?"  It connects with the official SDK, enters raw mode, and for every
accelerometer frame reports which of the 5 fingers actually carry data. It also
installs a tiny, non-invasive probe that records the RAW BLE-notification length
(without modifying the SDK), because that length is the root-cause signal:

    full accel frame = 4-byte header + 30-byte payload = 34 bytes
      * notification length >= 34  -> device sends whole frames -> all 5 fingers
      * notification length ~= 20  -> MTU-truncated -> trailing fingers lost
        (this is the "only 3 fingers" case; needs cross-notification reassembly)

Setup (once)
------------
    cd /Users/houzhen/research/paper_infocom_2027/tools/tapstrap_mac
    bash setup_tapstrap.sh           # creates .venv and installs bleak + official SDK
    source .venv/bin/activate

Before running
--------------
    1. In the TapManager app: enable "Developer Mode".
    2. Pair the Tap device in macOS System Settings > Bluetooth.

Run
---
    python3 tapstrap_mac_test.py            # 30s test, writes tap_raw_accel.csv
    python3 tapstrap_mac_test.py 60         # custom duration in seconds
"""

# --- macOS import gotcha (tap-python-sdk issue #10) ------------------------------
# On Apple Silicon, importing CoreBluetooth BEFORE bleak/tapsdk avoids the
# "requires the CoreBluetooth Framework" import error.
try:
    import CoreBluetooth  # noqa: F401
except Exception:
    pass

import asyncio
import csv
import sys
import time
from pathlib import Path

# Official SDK
from tapsdk import TapSDK, TapInputMode
from tapsdk import parsers  # we only read from it; see probe below

# --- finger layout (matches official Android RawSensorData: thumb,index,middle,ring,pinky)
FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
FULL_ACCEL_FRAME = 34  # 4-byte header + 30-byte payload
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

# ---------------------------------------------------------------------------------
# Non-invasive probe: wrap the SDK's raw parser to capture the raw notification
# length BEFORE parsing. We do NOT change parsing behavior — we just observe.
# ---------------------------------------------------------------------------------
PROBE = {"notif_lens": [], "last_len": 0}
_orig_raw_parser = parsers.raw_data_msg


def _probed_raw_parser(data):
    PROBE["last_len"] = len(data)
    PROBE["notif_lens"].append(len(data))
    return _orig_raw_parser(data)


parsers.raw_data_msg = _probed_raw_parser  # the posix backend calls parsers.raw_data_msg(...)


# ---------------------------------------------------------------------------------
# Collected state
# ---------------------------------------------------------------------------------
ACCEL = []  # list of (ts, [15 channels])


def on_raw_data(identifier, packets):
    # packets: list of {"type": "accl"|"imu", "ts": int, "payload": [...]}
    for m in packets:
        if m["type"] == "accl" and len(m["payload"]) >= 15:
            ACCEL.append((m["ts"], m["payload"][:15]))


def fingers_with_data(payload):
    return [FINGERS[i] for i in range(5) if any(payload[i * 3:i * 3 + 3])]


async def run(loop, duration):
    # 1. CHECK STATE: connect via official SDK.
    tap = TapSDK(loop=loop)
    await tap.run()
    if not tap.client.is_connected:
        print("[err] Not connected. Pair the Tap in macOS Bluetooth and enable "
              "Developer Mode in TapManager, then retry.", file=sys.stderr)
        return
    print(f"[conn] connected: {tap.client.is_connected}")
    try:
        mtu = tap.client.mtu_size
        print(f"[mtu ] negotiated ATT MTU = {mtu}  "
              f"(notification payload up to ~{mtu - 3}B; a full accel frame needs {FULL_ACCEL_FRAME}B)")
    except Exception as e:
        print(f"[mtu ] could not read mtu_size ({e})")

    # 2. ACT: subscribe to raw data, then enter raw sensors mode.
    #    (The posix backend auto-refreshes the mode every 10s to keep it alive.)
    await tap.register_raw_data_events(on_raw_data)
    await tap.set_input_mode(TapInputMode("raw", sensitivity=[0, 0, 0]))
    print(f"[mode] raw sensors mode set. Fingerspell for ~{duration}s ...\n")

    # 3. VERIFY: periodically report rate + per-finger coverage + raw notif length.
    t0 = time.time()
    last_n = 0
    while time.time() - t0 < duration:
        await asyncio.sleep(3)
        n = len(ACCEL)
        hz = (n - last_n) / 3.0
        last_n = n
        if n:
            cover = fingers_with_data(ACCEL[-1][1])
            avg_len = sum(PROBE["notif_lens"]) / max(1, len(PROBE["notif_lens"]))
            print(f"[t={time.time()-t0:4.0f}s] accel {n:6d} frames (~{hz:.0f} Hz) | "
                  f"raw notif: last={PROBE['last_len']}B avg={avg_len:.0f}B | "
                  f"fingers w/ data: {cover}")
        else:
            print(f"[t={time.time()-t0:4.0f}s] no accel frames yet "
                  f"(raw notif last={PROBE['last_len']}B)")

    # 4. DECIDE: write data + print a clear verdict.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "tap_raw_accel.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        header = ["ts_ms"] + [f"{fg}_{ax}" for fg in FINGERS for ax in "xyz"]
        w.writerow(header)
        for ts, payload in ACCEL:
            w.writerow([ts] + payload)

    print("\n" + "=" * 70)
    if not ACCEL:
        print("VERDICT: no raw frames received. Check Developer Mode + pairing.")
    else:
        # how many fingers ever carried data across the whole session
        ever = set()
        for _, p in ACCEL:
            ever.update(fingers_with_data(p))
        avg_len = sum(PROBE["notif_lens"]) / max(1, len(PROBE["notif_lens"]))
        print(f"frames={len(ACCEL)}  avg_raw_notif={avg_len:.0f}B  "
              f"fingers seen={sorted(ever, key=FINGERS.index)}")
        if len(ever) >= 5:
            print("VERDICT: ✅ official SDK delivers ALL 5 fingers on this Mac. "
                  "No reassembly needed — Mac is fully usable.")
        else:
            print("VERDICT: ⚠️ only %d fingers come through (avg notif ~%.0fB < %dB)."
                  % (len(ever), avg_len, FULL_ACCEL_FRAME))
            print("         The device is sending MTU-truncated notifications; the "
                  "official parser drops the trailing fingers.")
            print("         -> use tapstrap_mac_official_5finger.py to recover all 5 on Mac.")
    print(f"data written to: {out}")
    print("=" * 70)


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
