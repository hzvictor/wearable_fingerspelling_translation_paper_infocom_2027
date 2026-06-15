"""Headless integration test of the FULL collection flow — no GUI window, no hardware.

Drives the real CollectionController + store + sync through a complete session with
a fake BLE manager (synthetic 15-channel data) and a stub view that auto-accepts /
redoes / skips. Verifies:
  - PREP -> SPELLING -> DECIDE advances correctly
  - accept writes a trial_NNN.json with the unified schema + 15-channel payload
  - redo repeats the same trial number; skip leaves no file and advances
  - session meta is finalized
  - Firebase sync uploads the session and it reads back

Run:  arch -arm64 /usr/bin/python3 test_flow.py
"""
import struct
import time
import tkinter as tk

from core.models import Session, TrialDef
from core import store
from core.collection_controller import CollectionController
from core.paths import session_root


# ---- fakes -----------------------------------------------------------------

def _synthetic_buffer(n_accl=40, n_imu=40):
    """A realistic mixed buffer: 15-channel accl + 6-channel imu frames."""
    buf = []
    t = time.time()
    for i in range(max(n_accl, n_imu)):
        if i < n_accl:
            buf.append({"type": "accl", "ts": i,
                        "payload": [((i + c) % 50) - 25 for c in range(15)],
                        "recv_time": t + i * 0.005})
        if i < n_imu:
            buf.append({"type": "imu", "ts": i,
                        "payload": [c * 10 for c in range(6)],
                        "recv_time": t + i * 0.005})
    return buf


class FakeManager:
    def __init__(self):
        self.collecting = False
        self.recent = []
        self.max_accl_channels = 15
        self.device_name = "Tap_TEST"
        self.device_uuid = "test-uuid"
        self.packet_count = 0
        self._buf = []

    def start_collecting(self):
        self.collecting = True
        self._buf = []

    def stop_collecting(self):
        self.collecting = False
        self._buf = _synthetic_buffer()
        return self._buf

    def refresh_raw_mode(self):
        pass


class StubView:
    """Records render calls and auto-drives the decision after DECIDE."""
    def __init__(self, root, decisions):
        self.root = root
        self.decisions = list(decisions)   # e.g. ["accept","redo","accept","skip"]
        self.controller = None
        self.calls = {"prep": 0, "spelling": 0, "decide": 0}

    def render_prep(self, td, n, total, countdown):
        self.calls["prep"] += 1

    def render_spelling(self, td, n, total, hi, left):
        self.calls["spelling"] += 1

    def render_decide(self, td, n, total):
        self.calls["decide"] += 1

    def set_decision_enabled(self, enabled):
        if enabled and self.decisions:
            action = self.decisions.pop(0)
            self.root.after(5, lambda: getattr(self.controller, action)())


# ---- test ------------------------------------------------------------------

def run():
    root = tk.Tk()
    root.withdraw()  # no visible window

    subj_id = "S_TEST"
    sid = "TESTSESSION_" + time.strftime("%H%M%S")
    session = Session(id=sid, subject_id=subj_id, protocol_id="p_test",
                      device_name="Tap_TEST", target_trials=3,
                      started_at=time.time())
    # 3 trials: CAT, DOG, OX — fast (200ms collect each)
    trials = [
        TrialDef("CAT", list("CAT"), "confusion", duration_ms=200),
        TrialDef("DOG", list("DOG"), "common", duration_ms=200),
        TrialDef("OX", list("OX"), "common", duration_ms=200),
    ]
    # decisions: CAT accept, DOG redo then accept, OX skip
    view = StubView(root, ["accept", "redo", "accept", "skip"])

    done = {"flag": False, "saved": []}

    mgr = FakeManager()
    ctrl = CollectionController(
        root, mgr, view, session, trials,
        on_trial_saved=lambda i, td, tr: done["saved"].append((td.prompt, tr["trial"])),
        on_session_done=lambda: done.__setitem__("flag", True),
        prep_time=1.0)
    view.controller = ctrl
    ctrl.start()

    # pump the Tk loop until done (real time; ~6s for 4 prep+spell cycles)
    t0 = time.time()
    while not done["flag"] and time.time() - t0 < 25:
        root.update()
        time.sleep(0.01)

    root.destroy()

    # ---- assertions ----
    assert done["flag"], "session never completed"
    root_dir = session_root(sid)
    trial_files = sorted(root_dir.glob("trial_*.json"))
    print(f"trial files written: {[p.name for p in trial_files]}")
    print(f"on_trial_saved fired for: {done['saved']}")

    # CAT (trial 1) accepted, DOG (trial 2) redone+accepted, OX (trial 3) skipped
    names = {p.name for p in trial_files}
    assert "trial_001.json" in names, "CAT not saved"
    assert "trial_002.json" in names, "DOG not saved"
    assert "trial_003.json" not in names, "OX should have been skipped (no file)"

    import json
    cat = json.loads((root_dir / "trial_001.json").read_text())
    assert cat["word"] == "CAT" and cat["letters"] == ["C", "A", "T"], cat
    assert cat["num_letters"] == 3 and cat["group"] == "confusion", cat
    assert cat["trial"] == 1, cat
    accl = [m for m in cat["raw_data"] if m["type"] == "accl"]
    imu = [m for m in cat["raw_data"] if m["type"] == "imu"]
    assert accl and all(len(m["payload"]) == 15 for m in accl), "accl not 15-channel"
    assert imu and all(len(m["payload"]) == 6 for m in imu), "imu not 6-channel"
    assert cat["num_accl"] == len(accl) and cat["num_imu"] == len(imu), cat
    assert "recv_time" in accl[0] and "ts" in accl[0], "missing recv_time/ts"
    print(f"CAT schema OK: {cat['num_accl']} accl(15ch) + {cat['num_imu']} imu(6ch)")

    # finalize session meta (as CollectionScreen._on_done would)
    from core.models import Subject
    subj = Subject(id=subj_id, display_name="Test")
    session.ended_at = time.time(); session.completed = True
    session.max_accl_channels = 15
    store.write_session_meta(session, subj, "Test Protocol")
    meta = store.load_session_meta(sid)
    assert meta and meta["completed"] and meta["max_accl_channels"] == 15, meta
    print(f"session meta OK: completed={meta['completed']} ch={meta['max_accl_channels']}")

    # round-trip via store API
    loaded = store.load_session_trials(sid)
    assert len(loaded) == 2, f"expected 2 saved trials, got {len(loaded)}"
    print(f"store round-trip OK: {len(loaded)} trials")

    return sid


def test_sync(sid):
    """Actually push to Firebase and read back."""
    from sync import firebase
    cfg = firebase.load_config()
    if not cfg:
        print("sync: no firebase_config — skipped")
        return
    manifest = {}
    uploaded = firebase.sync_session_dir(cfg, sid, manifest)
    print(f"sync uploaded: {uploaded}")
    # read back the session doc
    import urllib.request, json, urllib.parse
    doc = f"{cfg['collector']}__{sid}"
    url = (f"https://firestore.googleapis.com/v1/projects/{cfg['projectId']}"
           f"/databases/(default)/documents/sessions/{urllib.parse.quote(doc)}"
           f"?key={cfg['apiKey']}")
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.loads(r.read())
    fields = d.get("fields", {})
    print(f"read-back session doc: trials={fields.get('total_trials',{}).get('integerValue')} "
          f"ch={fields.get('max_accl_channels',{}).get('integerValue')}")
    assert fields.get("total_trials", {}).get("integerValue") == "2", fields


def cleanup(sid):
    import shutil
    shutil.rmtree(session_root(sid), ignore_errors=True)
    print(f"cleaned up test session {sid}")


if __name__ == "__main__":
    sid = run()
    test_sync(sid)
    cleanup(sid)
    print("\n✅ FULL FLOW TEST PASSED")
