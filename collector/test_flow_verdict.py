"""Full-session flow test WITH the signal-quality verdict — headless, no hardware.

Drives the real CollectionController; a StubView computes the verdict at DECIDE
exactly as CollectionCanvas.render_decide does (from controller._pending_trial).
Asserts GOOD trials verdict GOOD with proper confirmation copy, and a starved
trial (Tap "disconnected") yields BAD + a "Please redo" message.

Run: arch -arm64 /usr/bin/python3 test_flow_verdict.py
"""
import time
import tkinter as tk

from core.models import Session, TrialDef
from core.collection_controller import CollectionController
from core.signal_quality import signal_quality
from core.paths import session_root


def synth(n_accl, n_imu=40, fingers=5, channels=15):
    out = []
    for i in range(n_accl):
        pl = []
        for f in range(channels // 3):
            pl += ([((i+f) % 30)+1, 2, 3] if f < fingers else [0, 0, 0])
        pl += [0] * (channels - len(pl))
        out.append({"type": "accl", "ts": i, "payload": pl, "recv_time": time.time()+i*0.005})
    for i in range(n_imu):
        out.append({"type": "imu", "ts": i, "payload": [0,0,0,1,2,3], "recv_time": time.time()+i*0.005})
    return out


class FakeManager:
    """Returns a GOOD buffer normally; a starved buffer for the trial whose word
    is in `starve`."""
    def __init__(self, starve):
        self.collecting = False
        self.recent = []
        self.max_accl_channels = 15
        self.device_name = "Tap_TEST"; self.device_uuid = "u"; self.packet_count = 0
        self.starve = starve
        self._word = None
    def start_collecting(self): self.collecting = True
    def stop_collecting(self):
        self.collecting = False
        if self._word in self.starve:
            return synth(15, fingers=2)        # BAD: few frames + 2 fingers
        return synth(760, fingers=5)            # GOOD
    def refresh_raw_mode(self): pass


class StubView:
    def __init__(self, root, decisions, mgr):
        self.root = root; self.decisions = list(decisions); self.mgr = mgr
        self.controller = None
        self.verdicts = []        # (word, level, summary)
    def render_prep(self, td, n, total, c): self.mgr._word = td.prompt
    def render_spelling(self, td, n, total, hi, left): pass
    def render_decide(self, td, n, total):
        pending = self.controller._pending_trial
        v = signal_quality(pending["raw_data"], pending["collect_time"])
        self.verdicts.append((td.prompt, v.level, v.summary(td.prompt), v.decide_banner()))
    def set_decision_enabled(self, enabled):
        if enabled and self.decisions:
            self.root.after(5, lambda: getattr(self.controller, self.decisions.pop(0))())


def run():
    root = tk.Tk(); root.withdraw()
    sid = "VERDICT_" + time.strftime("%H%M%S")
    session = Session(id=sid, subject_id="S", protocol_id="p", target_trials=2,
                      started_at=time.time())
    trials = [TrialDef("CAT", list("CAT"), "c", duration_ms=200),
              TrialDef("DOG", list("DOG"), "c", duration_ms=200)]
    mgr = FakeManager(starve={"DOG"})        # DOG will be BAD
    view = StubView(root, ["accept", "accept"], mgr)
    done = {"flag": False}
    ctrl = CollectionController(root, mgr, view, session, trials,
                               on_trial_saved=lambda i, td, tr: None,
                               on_session_done=lambda: done.__setitem__("flag", True),
                               prep_time=1.0)
    view.controller = ctrl
    ctrl.start()
    t0 = time.time()
    while not done["flag"] and time.time() - t0 < 25:
        root.update(); time.sleep(0.01)
    root.destroy()

    assert done["flag"], "session never completed"
    for word, level, summary, banner in view.verdicts:
        print(f"  {word}: {level}  summary={summary!r}  banner={banner!r}")
    by_word = {w: (lvl, summ, ban) for w, lvl, summ, ban in view.verdicts}

    # CAT good
    assert by_word["CAT"][0] == "GOOD", by_word["CAT"]
    assert "CAT" in by_word["CAT"][1] and "frames" in by_word["CAT"][1] and "fingers" in by_word["CAT"][1]
    assert by_word["CAT"][2] == "✓ Good capture — Accept", by_word["CAT"][2]
    # DOG bad
    assert by_word["DOG"][0] == "BAD", by_word["DOG"]
    assert "redo" in by_word["DOG"][1].lower(), by_word["DOG"][1]
    assert "Redo" in by_word["DOG"][2], by_word["DOG"][2]

    # cleanup
    import shutil
    shutil.rmtree(session_root(sid), ignore_errors=True)
    print("\n✅ FLOW+VERDICT TEST PASSED")


if __name__ == "__main__":
    run()
