"""Drive the CoreBluetooth NSRunLoop from inside Tkinter's mainloop.

CoreBluetooth delivers notifications on the run loop of the thread that owns the
CBCentralManager (the main thread here). Tkinter's mainloop owns the same
thread, so we interleave: every `tick_ms` we hand control to NSRunLoop for a
tiny `slice_s` to drain BLE callbacks, then re-arm via root.after(). Tk stays
responsive; the ~190 Hz stream is fully drained (the old blocking 20 ms loop was
lossless, so this has margin). No background thread — pyobjc + secondary run
loops are fragile.
"""
from Foundation import NSRunLoop, NSDate


class RunLoopPump:
    def __init__(self, tk_root, tick_ms=15, slice_s=0.005):
        self.root = tk_root
        self.tick_ms = tick_ms
        self.slice_s = slice_s
        self._running = False

    def start(self):
        self._running = True
        self._tick()

    def _tick(self):
        if not self._running:
            return
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(self.slice_s))
        self.root.after(self.tick_ms, self._tick)

    def stop(self):
        self._running = False


def pump_for(seconds: float, slice_s: float = 0.02):
    """Blocking pump for a fixed duration — used in headless spikes/tests only,
    NOT inside the GUI (which uses RunLoopPump). Ported from collect_gestures.run_loop."""
    import time
    end = time.time() + seconds
    loop = NSRunLoop.currentRunLoop()
    while time.time() < end:
        loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(slice_s))


def wait_for_ready(manager, timeout: float = 15.0) -> bool:
    """Pump the run loop until the manager reaches 'ready' or 'done'. Headless only."""
    import time
    end = time.time() + timeout
    loop = NSRunLoop.currentRunLoop()
    while time.time() < end:
        loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))
        if manager.phase == "ready":
            return True
        if manager.phase == "done":
            return False
    return False
