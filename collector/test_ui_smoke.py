"""Headless construct+render smoke test for every CustomTkinter screen.

Builds each screen with a FakeApp stand-in (no CoreBluetooth, no display
interaction), calls on_show, and root.update()s — asserting no exception. This
catches the bulk of migration breakage. Writes PASS/FAIL to a result file because
macOS Aqua Tk swallows stdout under the headless harness.

Run: arch -arm64 /usr/bin/python3 test_ui_smoke.py ; cat /tmp/ui_smoke_result.txt
"""
import sys
import traceback
from collections import deque

import customtkinter as ctk

from core.models import Subject, Protocol, TrialDef, Session

RESULT = "/tmp/ui_smoke_result.txt"


class FakeManager:
    def __init__(self):
        self.recent = deque(maxlen=300)
        self.max_accl_channels = 15
        self.device_name = "Tap_TEST"
        self.device_uuid = "uuid"
        self.collecting = False
        self.phase = "ready"
        # seed some live frames so the strip has data
        for k in range(20):
            self.recent.append({"type": "accl", "ts": k,
                                "payload": [30, -20, 10] * 5, "recv_time": k})

    def start_collecting(self): self.collecting = True
    def stop_collecting(self): self.collecting = False; return list(self.recent)
    def refresh_raw_mode(self): pass


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.container = ctk.CTkFrame(root)
        self.container.pack(fill="both", expand=True)
        self.manager = FakeManager()
        self.ble_state = "powered_on"
        self.ble_error = ""
        self.selected_subject = Subject(id="S001", display_name="Test", consent_at=1.0)
        self.selected_protocol = Protocol(id="p", name="Test Protocol", type="word",
                                          trials=[TrialDef("CAT", list("CAT"), "confusion")])
        self.session = Session(id="20260101_000000", subject_id="S001", protocol_id="p",
                               target_trials=1)
        self.session_trials = self.selected_protocol.trials
        self.controller = None

    def device_ready(self): return True
    def reconnect(self): pass
    def navigate(self, name, **kw): pass


def main():
    ctk.set_appearance_mode("dark")
    root = ctk.CTk(); root.withdraw()

    from ui.home import HomeScreen
    from ui.device import DeviceScreen
    from ui.subjects import SubjectsScreen
    from ui.session_setup import SessionSetupScreen
    from ui.sessions import SessionsScreen
    from ui.collection import CollectionScreen

    screens = [
        ("home", HomeScreen), ("device", DeviceScreen), ("subjects", SubjectsScreen),
        ("session_setup", SessionSetupScreen), ("sessions", SessionsScreen),
        ("collection", CollectionScreen),
    ]
    results = []
    for name, cls in screens:
        app = FakeApp(root)
        try:
            screen = cls(app)
            screen.pack(fill="both", expand=True)
            if hasattr(screen, "on_show"):
                screen.on_show()
            root.update()
            root.update()
            results.append((name, "ok"))
        except Exception:
            results.append((name, "FAIL\n" + traceback.format_exc()))
        finally:
            app.container.destroy()

    root.destroy()
    failed = [r for r in results if r[1] != "ok"]
    with open(RESULT, "w") as f:
        for name, r in results:
            f.write(f"{name}: {r}\n")
        f.write("\n" + ("✅ ALL UI SMOKE PASSED" if not failed
                        else f"❌ {len(failed)} screen(s) FAILED"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
