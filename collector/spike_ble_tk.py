"""Phase 1 spike: prove the Tap Strap connects and streams 15-channel data
INSIDE a Tkinter window, with CoreBluetooth's NSRunLoop pumped from root.after().

This is the highest-risk integration (GUI mainloop + CoreBluetooth run loop on the
same thread). If this shows MTU-driven 182-byte notifications -> 15 accl channels
@ ~190 Hz while the Tk window stays responsive, the foundation is proven.

Run:  /usr/bin/python3 spike_ble_tk.py
Prereq: Tap connected to this Mac as a keyboard + TapManager Developer Mode ON.
        Tap fingers (all 5) to generate data.
"""
import time
import tkinter as tk

from CoreBluetooth import CBCentralManager

from ble.manager import TapBleManager
from ble.runloop import RunLoopPump
import config


class SpikeApp:
    def __init__(self, root):
        self.root = root
        root.title("Phase 1 — BLE in Tk")
        root.configure(bg="#1a1a2e")

        self.status = tk.StringVar(value="starting…")
        self.metrics = tk.StringVar(value="")
        tk.Label(root, textvariable=self.status, fg="#e94560", bg="#1a1a2e",
                 font=("Helvetica", 18, "bold")).pack(pady=(24, 8), padx=24)
        tk.Label(root, textvariable=self.metrics, fg="#ddd", bg="#1a1a2e",
                 font=("Menlo", 14), justify="left").pack(pady=8, padx=24)
        tk.Button(root, text="Start collecting (tap fingers)",
                  command=self.toggle).pack(pady=8)
        self.collect_btn_on = False

        # BLE manager + central on the main thread
        self.mgr = TapBleManager.alloc().init()
        self.mgr.on_state = lambda s: self.status.set(f"bluetooth: {s}")
        self.mgr.on_ready = lambda: self.status.set("READY — raw mode armed ✓")
        self.mgr.on_error = lambda m: self.status.set(f"⚠ {m}")
        self.central = CBCentralManager.alloc().initWithDelegate_queue_(self.mgr, None)

        # pump CoreBluetooth from Tk
        self.pump = RunLoopPump(root, config.PUMP_TICK_MS, config.PUMP_SLICE_S)
        self.pump.start()

        self._t0 = time.time()
        self._last_count = 0
        self._refresh()

    def toggle(self):
        if not self.collect_btn_on:
            self.mgr.start_collecting()
            self.collect_btn_on = True
        else:
            self.mgr.stop_collecting()
            self.collect_btn_on = False

    def _refresh(self):
        m = self.mgr
        # frame rate from the recent ring buffer
        accl = sum(1 for x in m.recent if x["type"] == "accl")
        imu = sum(1 for x in m.recent if x["type"] == "imu")
        last_accl = next((x for x in reversed(m.recent) if x["type"] == "accl"), None)
        fingers = []
        if last_accl:
            pl = last_accl["payload"]
            names = ["thumb", "index", "middle", "ring", "pinky"]
            fingers = [names[i] for i in range(min(5, len(pl)//3)) if any(pl[i*3:i*3+3])]
        self.metrics.set(
            f"max accl channels : {m.max_accl_channels}   (target {config.TARGET_ACCL_CHANNELS})\n"
            f"recent buffer      : {accl} accl / {imu} imu frames\n"
            f"fingers w/ data    : {fingers}\n"
            f"collecting         : {m.collecting}   trial packets: {m.packet_count}"
        )
        self.root.after(200, self._refresh)


if __name__ == "__main__":
    root = tk.Tk()
    SpikeApp(root)
    try:
        root.mainloop()
    finally:
        pass
