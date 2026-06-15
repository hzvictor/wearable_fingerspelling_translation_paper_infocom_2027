"""
TapStrap raw test on macOS — OFFICIAL tap-python-sdk with a MINIMAL connection patch.

What is patched, and ONLY this:
    The official posix backend finds the device exclusively via
    retrieveConnectedPeripheralsWithServices_(), which returns nothing when the
    Tap is bonded to macOS as an HID keyboard (and the SDK never scans). So we
    replace JUST the "find + connect" step with a BleakScanner scan + bleak
    connect. Everything else is stock official SDK:
        - tap.register_raw_data_events(...)   (official)
        - tap.set_input_mode(TapInputMode("raw", ...))  (official, incl. 10s auto-refresh)
        - tapsdk.parsers.raw_data_msg          (official parser, UNCHANGED)

A non-invasive probe wraps (but does not alter) the official parser to record the
raw BLE-notification length, so we can SEE whether the official path yields 5
fingers or the truncated 3.

Run:
    source .venv/bin/activate
    python3 tapstrap_mac_official_patched.py [duration_seconds]
"""

try:
    import CoreBluetooth  # noqa: F401  (precede bleak import on Apple Silicon)
except Exception:
    pass

import asyncio
import csv
import sys
import time

from bleak import BleakScanner
from tapsdk import TapSDK, TapInputMode
from tapsdk import parsers  # official parser; we only observe it

FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
FULL_ACCEL_FRAME = 34  # 4-byte header + 30-byte payload

# --- non-invasive probe: observe raw notification length, then delegate to official parser
PROBE = {"lens": [], "last": 0}
_official_parser = parsers.raw_data_msg


def _observed_parser(data):
    PROBE["last"] = len(data)
    PROBE["lens"].append(len(data))
    return _official_parser(data)        # behavior unchanged — official parsing


# The official parser references its OWN function attribute by global name
# (raw_data_msg.msg_type_value). Since we rebind parsers.raw_data_msg below,
# copy that attribute onto our wrapper so the official body still finds it.
_observed_parser.msg_type_value = getattr(_official_parser, "msg_type_value", 2 ** 31)
parsers.raw_data_msg = _observed_parser

ACCEL = []


def on_raw_data(identifier, packets):
    for m in packets:
        if m["type"] == "accl" and len(m["payload"]) >= 15:
            ACCEL.append((m["ts"], m["payload"][:15]))


def fingers_with_data(p):
    return [FINGERS[i] for i in range(5) if any(p[i * 3:i * 3 + 3])]


async def connect_official_with_scan(loop):
    """MINIMAL PATCH: scan for the Tap, then drive the official SDK's own bleak
    client to connect — instead of the SDK's retrieveConnectedPeripheralsWithServices_."""
    print("[scan] scanning for Tap (replaces official retrieveConnected) ...")
    dev = await BleakScanner.find_device_by_filter(
        lambda d, ad: (d.name or "").lower().startswith("tap"), timeout=15.0)
    if not dev:
        print("[err] Tap not advertising. In macOS Bluetooth, the Tap must be in "
              "'Nearby Devices' (advertising), not actively connected as a keyboard.",
              file=sys.stderr)
        return None
    print(f"[scan] found {dev.name} ({dev.address})")

    # Connect with retries: the device may require a one-time pairing ("Connection
    # Request" dialog -> click Connect), and macOS can transiently drop the link
    # while it stops treating the Tap as an HID keyboard. Retry a few times.
    last_err = None
    for attempt in range(1, 6):
        tap = TapSDK(loop=loop, address=dev.address)
        try:
            await tap.client.connect()
            await tap.client.get_services()
            print(f"[conn] connected={tap.client.is_connected}  "
                  f"mtu={getattr(tap.client,'mtu_size','?')}  (attempt {attempt})")
            return tap
        except Exception as e:
            last_err = e
            print(f"[conn] attempt {attempt} failed: {e} -> retrying in 2s "
                  f"(if a 'Connection Request' dialog appears, click Connect)")
            try:
                await tap.client.disconnect()
            except Exception:
                pass
            await asyncio.sleep(2)
    print(f"[err] could not establish a stable connection: {last_err}", file=sys.stderr)
    return None


async def run(loop, duration):
    tap = await connect_official_with_scan(loop)
    if not tap:
        return

    # ---- from here on: 100% stock official SDK ----
    await tap.register_raw_data_events(on_raw_data)
    await tap.set_input_mode(TapInputMode("raw", sensitivity=[0, 0, 0]))
    print(f"[mode] official raw mode set. Fingerspell for ~{duration}s ...\n")

    t0 = time.time()
    last = 0
    while time.time() - t0 < duration:
        await asyncio.sleep(3)
        n = len(ACCEL)
        hz = (n - last) / 3.0
        last = n
        if n:
            avg = sum(PROBE["lens"]) / max(1, len(PROBE["lens"]))
            print(f"[t={time.time()-t0:4.0f}s] accel {n:6d} (~{hz:.0f} Hz) | "
                  f"raw notif last={PROBE['last']}B avg={avg:.0f}B | "
                  f"fingers w/ data: {fingers_with_data(ACCEL[-1][1])}")
        else:
            print(f"[t={time.time()-t0:4.0f}s] no accel yet (notif last={PROBE['last']}B)")

    out = "tap_raw_accel_official.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_ms"] + [f"{fg}_{ax}" for fg in FINGERS for ax in "xyz"])
        for ts, p in ACCEL:
            w.writerow([ts] + p)

    print("\n" + "=" * 70)
    if not ACCEL:
        print("VERDICT: connected via official SDK, but no raw frames. "
              "Check Developer Mode in TapManager.")
    else:
        ever = set()
        for _, p in ACCEL:
            ever.update(fingers_with_data(p))
        avg = sum(PROBE["lens"]) / max(1, len(PROBE["lens"]))
        print(f"OFFICIAL SDK result: frames={len(ACCEL)}  avg_notif={avg:.0f}B  "
              f"fingers seen={sorted(ever, key=FINGERS.index)}")
        if len(ever) >= 5:
            print("VERDICT: ✅ official SDK (connection-patched) gives ALL 5 fingers.")
        else:
            print(f"VERDICT: ⚠️ official SDK gives only {len(ever)} fingers "
                  f"(notif ~{avg:.0f}B < {FULL_ACCEL_FRAME}B needed).")
            print("         Connection is fixed; the remaining loss is the official "
                  "PARSER not reassembling MTU-split frames — a separate 1-function fix.")
    print(f"data -> {out}")
    print("=" * 70)


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
