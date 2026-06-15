"""Collection controller — the PREP -> SPELLING -> DECIDE trial loop.

Replaces the old blocking `collect_word_trial` (collect_words.py:442-513) with a
tk.after-chained state machine so the GUI never freezes. The BLE buffer fills via
the RunLoopPump in parallel; this controller only schedules timing and builds the
unified word-shaped trial dict.

The `view` it drives must implement:
    render_prep(td, trial_num, total, countdown:int)
    render_spelling(td, trial_num, total, highlight_idx:int, seconds_left:float)
    render_decide(td, trial_num, total)
    set_decision_enabled(enabled:bool)
"""
from __future__ import annotations
import time

from . import audio
from . import store
from .models import TrialDef, Session
from config import DEFAULT_PREP_TIME_S, RAW_REFRESH_INTERVAL_S


class CollectionController:
    def __init__(self, root, manager, view, session: Session,
                 trials: list[TrialDef],
                 on_trial_saved=lambda i, td, trial: None,
                 on_session_done=lambda: None,
                 prep_time: float = DEFAULT_PREP_TIME_S):
        self.root = root
        self.mgr = manager
        self.view = view
        self.session = session
        self.trials = trials
        self.on_trial_saved = on_trial_saved
        self.on_session_done = on_session_done
        self.prep_time = prep_time

        self.idx = 0
        self._start_time = 0.0
        self._collect_time = 0.0
        self._after_ids: list[str] = []
        self._last_refresh = 0.0

    # ---- lifecycle ----

    def start(self):
        self.idx = 0
        self._run_trial()

    def cancel(self):
        for aid in self._after_ids:
            try:
                self.root.after_cancel(aid)
            except Exception:
                pass
        self._after_ids.clear()
        if self.mgr.collecting:
            self.mgr.stop_collecting()

    def _after(self, ms, fn):
        aid = self.root.after(ms, fn)
        self._after_ids.append(aid)
        return aid

    # ---- PREP ----

    def _run_trial(self):
        if self.idx >= len(self.trials):
            self.on_session_done()
            return
        td = self.trials[self.idx]
        self.view.set_decision_enabled(False)
        audio.say(f"Please spell {td.prompt}")
        self._maybe_refresh_raw()
        n = max(1, int(round(self.prep_time)))
        self._prep_step(td, n)

    def _prep_step(self, td: TrialDef, remaining: int):
        self.view.render_prep(td, self.idx + 1, len(self.trials), remaining)
        if remaining <= 0:
            self._begin_spelling(td)
            return
        audio.beep()
        self._after(1000, lambda: self._prep_step(td, remaining - 1))

    # ---- SPELLING ----

    def _begin_spelling(self, td: TrialDef):
        self._collect_time = td.collect_time()
        self._start_time = time.time()
        self.mgr.start_collecting()
        audio.beep_start()
        n_letters = max(1, len(td.letters))
        self._per_letter_ms = int(self._collect_time / n_letters * 1000)
        self._advance_letter(td, 0)

    def _advance_letter(self, td: TrialDef, li: int):
        n_letters = max(1, len(td.letters))
        if li >= n_letters:
            self._finish_spelling(td)
            return
        elapsed = time.time() - self._start_time
        seconds_left = max(0.0, self._collect_time - elapsed)
        self.view.render_spelling(td, self.idx + 1, len(self.trials), li, seconds_left)
        self._maybe_refresh_raw()
        self._after(self._per_letter_ms, lambda: self._advance_letter(td, li + 1))

    def _finish_spelling(self, td: TrialDef):
        raw = self.mgr.stop_collecting()
        audio.beep_done()
        self._pending_trial = self.build_trial(td, raw)
        self.view.render_decide(td, self.idx + 1, len(self.trials))
        self.view.set_decision_enabled(True)

    # ---- DECIDE (called by view buttons / key bindings) ----

    def accept(self):
        if not getattr(self, "_pending_trial", None):
            return
        trial = self._pending_trial
        store.write_trial(self.session.id, trial)
        self.on_trial_saved(self.idx, self.trials[self.idx], trial)
        self._pending_trial = None
        self.idx += 1
        self._run_trial()

    def redo(self):
        audio.say("Redo")
        self._pending_trial = None
        self._run_trial()   # same idx

    def skip(self):
        audio.say("Skipped")
        self._pending_trial = None
        self.idx += 1
        self._run_trial()

    # ---- helpers ----

    def _maybe_refresh_raw(self):
        now = time.time()
        if now - self._last_refresh > RAW_REFRESH_INTERVAL_S:
            self.mgr.refresh_raw_mode()
            self._last_refresh = now

    def build_trial(self, td: TrialDef, raw: list[dict]) -> dict:
        """Unified word-shaped trial dict (compatible with prepare_finetune_data.py)."""
        n_accl = sum(1 for m in raw if m["type"] == "accl")
        n_imu = sum(1 for m in raw if m["type"] == "imu")
        return {
            "word": td.prompt,
            "letters": list(td.letters),
            "num_letters": len(td.letters),
            "group": td.group,
            "confusion_test": td.confusion_test,
            "trial": self.idx + 1,
            "collect_time": round(self._collect_time, 3),
            "timestamp": self._start_time,
            "num_packets": len(raw),
            "num_accl": n_accl,
            "num_imu": n_imu,
            "raw_data": raw,
        }
