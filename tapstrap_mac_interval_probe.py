"""
Rigorously measure the macOS BLE ceiling for TapStrap raw mode:
  - read the device's Preferred Connection Parameters (GATT 0x2A04)
  - timestamp every NUS notification and build an inter-arrival histogram
  - report bytes/s, notif/s, and whether packets ever arrive in bursts
    (bursts => macOS packs multiple notifications per connection event,
     i.e. the ceiling is NOT 1-packet-per-interval)
"""
import asyncio, struct, sys, time
from collections import Counter
from bleak import BleakScanner, BleakClient

NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
PPCP   = "00002a04-0000-1000-8000-00805f9b34fb"   # Peripheral Preferred Connection Parameters
RAW_MODE_CMD = bytes([0x03, 0x0C, 0x00, 0x0A, 0x00, 0x00, 0x00])

times = []
total_bytes = [0]

def on_notify(_c, data):
    times.append(time.perf_counter())
    total_bytes[0] += len(data)

async def main(duration):
    dev = None
    for st in range(1, 9):                  # ~40s of retries; wiggle fingers to wake/advertise
        print(f"[scan] try {st}/8 (wiggle fingers to keep it advertising) ...")
        dev = await BleakScanner.find_device_by_filter(
            lambda d, ad: (d.name or "").lower().startswith("tap"), timeout=5.0)
        if dev:
            break
    if not dev:
        print("[err] Tap never advertised (still bonded as keyboard / asleep)."); return
    print(f"[scan] {dev.name} {dev.address}")
    # connect with retry; the pairing dialog ("Connection Request" -> click Connect)
    # can delay service discovery, so wait until services are actually present.
    c = None
    for attempt in range(1, 7):
        c = BleakClient(dev)
        try:
            await c.connect()
            for _ in range(20):                 # wait up to ~10s for service discovery
                try:
                    if list(c.services):
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            if c.is_connected and list(c.services):
                break
            raise RuntimeError("services not discovered (click Connect on the pairing dialog)")
        except Exception as e:
            print(f"[conn] attempt {attempt} not ready: {e} -> retry "
                  f"(click Connect if a pairing dialog shows)")
            try:
                await c.disconnect()
            except Exception:
                pass
            await asyncio.sleep(2)
    if not (c and c.is_connected):
        print("[err] could not complete connection.")
        return
    try:
        print(f"[conn] mtu={c.mtu_size}")
        # read preferred connection parameters if exposed
        try:
            v = await c.read_gatt_char(PPCP)
            if len(v) >= 8:
                min_i, max_i, lat, to = struct.unpack("<HHHH", v[:8])
                print(f"[PPCP] min_interval={min_i*1.25:.2f}ms  max_interval={max_i*1.25:.2f}ms  "
                      f"slave_latency={lat}  timeout={to*10}ms")
        except Exception as e:
            print(f"[PPCP] not readable: {e}")

        await c.start_notify(NUS_TX, on_notify)
        await c.write_gatt_char(NUS_RX, RAW_MODE_CMD, response=False)
        print(f"[run ] streaming {duration}s ...")
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < duration:
            await asyncio.sleep(2)
            await c.write_gatt_char(NUS_RX, RAW_MODE_CMD, response=False)
        mtu = c.mtu_size
    finally:
        try:
            await c.disconnect()
        except Exception:
            pass

    el = times[-1] - times[0] if len(times) > 1 else 1
    n = len(times)
    deltas = [(times[i] - times[i-1]) * 1000 for i in range(1, n)]  # ms
    # histogram in 2ms buckets
    hist = Counter(int(d // 2) * 2 for d in deltas)
    bursts = sum(1 for d in deltas if d < 2.0)   # <2ms apart = same connection event
    print("\n" + "=" * 70)
    print(f"notifications: {n}  over {el:.1f}s  = {n/el:.0f}/s")
    print(f"throughput   : {total_bytes[0]/el:.0f} B/s")
    print(f"inter-arrival ms histogram (2ms buckets): "
          f"{dict(sorted(hist.items()))}")
    if deltas:
        ds = sorted(deltas)
        print(f"median gap={ds[len(ds)//2]:.1f}ms  min={ds[0]:.2f}ms  "
              f"p90={ds[int(len(ds)*0.9)]:.1f}ms")
    print(f"back-to-back (<2ms) packets: {bursts}/{len(deltas)} "
          f"-> {'PACKING happens (ceiling is NOT 1/interval)' if bursts>len(deltas)*0.1 else 'NO packing: ~1 packet per connection event'}")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 15))
