"""ASL Fingerspelling Collector — entry point.

Wires: Tk root + a CBCentralManager (delegate = TapBleManager) + a RunLoopPump
that drives CoreBluetooth from inside Tk's mainloop + a Router over the screens.
Local JSON is the source of truth; Firebase sync runs best-effort on a daemon
thread after each session.

Run from source:  /usr/bin/python3 app.py
"""
import time

# CustomTkinter polls OS dark/light mode every 30 ms via app.after -> darkdetect.theme(),
# which on macOS is a native ObjC call. Executed inside our RunLoopPump (which drives the
# NSRunLoop manually), that native call faults with "PyEval_RestoreThread ... GIL released".
# We hard-set dark mode and never change it, so replace darkdetect's native probes with
# pure-Python constants BEFORE CustomTkinter uses them. (Must run before `import customtkinter`.)
import darkdetect as _darkdetect
_darkdetect.theme = lambda: "Dark"
_darkdetect.listener = lambda *a, **k: None

import customtkinter as ctk

from CoreBluetooth import CBCentralManager

from ble.manager import TapBleManager
from ui.router import Router
from ui import theme
import config

from ui.home import HomeScreen
from ui.device import DeviceScreen
from ui.subjects import SubjectsScreen
from ui.session_setup import SessionSetupScreen
from ui.sessions import SessionsScreen
from ui.collection import CollectionScreen


class App:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.root = ctk.CTk()
        self.root.title(config.WINDOW_TITLE)
        self.root.minsize(*config.WINDOW_MIN_SIZE)
        self.root.configure(fg_color=theme.BG)

        # ---- BLE (main thread) ----
        self.ble_state = "unknown"
        self.ble_error = ""
        self.manager = TapBleManager.alloc().init()
        self.manager.on_state = self._on_ble_state
        self.manager.on_ready = self._on_ble_ready
        self.manager.on_error = self._on_ble_error
        # CoreBluetooth on the main queue (None). On macOS, Tk's mainloop already
        # drives the Cocoa/NSRunLoop, so delegate callbacks (state + notifications)
        # arrive without a manual pump. A manual nested NSRunLoop pump conflicts
        # with CustomTkinter's Cocoa integration and faults the GIL, so we don't
        # use one. The always-on `after` timers (finger strip, dashboards) keep the
        # run loop serviced during idle periods.
        self.central = CBCentralManager.alloc().initWithDelegate_queue_(self.manager, None)

        # ---- shared navigation state ----
        self.selected_subject = None     # Subject
        self.selected_protocol = None    # Protocol
        self.selected_groups = None      # set[str] | None (None = all)
        self.session = None              # Session
        self.controller = None

        # ---- router + screens ----
        self.container = ctk.CTkFrame(self.root, fg_color=theme.BG)
        self.container.pack(fill="both", expand=True)
        self.router = Router(self.container)
        self.router.register("home", lambda: HomeScreen(self))
        self.router.register("device", lambda: DeviceScreen(self))
        self.router.register("subjects", lambda: SubjectsScreen(self))
        self.router.register("session_setup", lambda: SessionSetupScreen(self))
        self.router.register("sessions", lambda: SessionsScreen(self))
        self.router.register("collection", lambda: CollectionScreen(self))

        self.router.show("home")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- BLE callbacks (forwarded to whichever screen cares via on_show refresh) ----

    def _on_ble_state(self, s):
        self.ble_state = s
        self.ble_error = ""

    def _on_ble_ready(self):
        self.ble_state = "ready"
        self.ble_error = ""

    def _on_ble_error(self, m):
        self.ble_error = m

    def device_ready(self) -> bool:
        return self.manager.phase == "ready"

    def reconnect(self):
        """Re-attempt connect (Tap must be awake + connected to Mac as keyboard)."""
        if self.central is not None and self.central.state() == 5:
            self.manager._find_and_connect(self.central)

    # ---- navigation ----

    def navigate(self, name, **kw):
        self.router.show(name, **kw)

    # ---- lifecycle ----

    def run(self):
        # force a first layout/paint + bring to front before the event loop
        self.root.update_idletasks()
        self.root.deiconify()
        self.root.lift()
        self.root.mainloop()

    def _on_close(self):
        try:
            self.manager.finish()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    App().run()
