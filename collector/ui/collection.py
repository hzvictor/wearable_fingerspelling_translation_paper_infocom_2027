"""Active-collection screen — participant-centric.

Always-visible: subject · protocol · "Trial X/N" + progress bar (WHERE AM I).
During spelling: the FingerActivityStrip shows live finger motion (DID IT RECORD).
At DECIDE: the canvas banner shows the GOOD/WEAK/BAD verdict before committing.
After Accept: an ephemeral confirmation ("✓ CAT saved · N frames · 5 fingers").
A watchdog pauses the session if the Tap disconnects (no silent empty trials).
On completion: a clear "Session complete" panel.
"""
import time
import customtkinter as ctk

from . import theme, widgets
from .collection_canvas import CollectionCanvas
from .signal_strip import FingerActivityStrip
from core.collection_controller import CollectionController
from core import store
from sync import syncer


class CollectionScreen(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app.container, fg_color=theme.BG)
        self.app = app

        # persistent header: subject · protocol · Trial X/N + progress bar
        head = ctk.CTkFrame(self, fg_color=theme.BG)
        head.pack(fill="x", padx=24, pady=(14, 4))
        self.ctx_lbl = ctk.CTkLabel(head, text="", text_color=theme.TEXT,
                                    font=(theme.FONT, 13, "bold"))
        self.ctx_lbl.pack(side="left")
        self.count_lbl = ctk.CTkLabel(head, text="", text_color=theme.TEXT_MUTED,
                                      font=(theme.FONT, 12))
        self.count_lbl.pack(side="right")
        self.progress = ctk.CTkProgressBar(self, progress_color=theme.ACCENT)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=24, pady=(0, 6))

        # confirmation strip (post-accept)
        self.confirm = ctk.CTkLabel(self, text="", text_color=theme.GOOD,
                                    font=(theme.FONT, 13, "bold"))
        self.confirm.pack(pady=(0, 2))

        self.canvas = CollectionCanvas(self, lambda: self.app.controller)
        self.canvas.pack(fill="both", expand=True)

        # live finger strip
        self.strip = FingerActivityStrip(self, app.manager, label="LIVE — your finger motion")
        self.strip.pack(pady=(0, 8))

        self._keys_bound = False
        self._was_ready = True
        self._active = False

    def on_show(self):
        session = self.app.session
        trials = getattr(self.app, "session_trials", [])
        if not session or not trials:
            self.app.navigate("home")
            return
        if not self._keys_bound:
            self.canvas.bind_keys(self.app.root)
            self._keys_bound = True
        self._total = len(trials)
        self.ctx_lbl.configure(
            text=f"{session.subject_id} · {self.app.selected_protocol.name}")
        self._set_progress(0)
        self.confirm.configure(text="")
        self.strip.start()
        self._active = True
        self._was_ready = self.app.device_ready()
        self.app.controller = CollectionController(
            self.app.root, self.app.manager, self.canvas, session, trials,
            on_trial_saved=self._on_trial_saved, on_session_done=self._on_done)
        self.app.controller.start()
        self._watchdog()

    def _set_progress(self, done):
        self.count_lbl.configure(text=f"Trial {min(done+1, self._total)} / {self._total}")
        self.progress.set(done / self._total if self._total else 0)

    def _on_trial_saved(self, idx, td, trial):
        self._set_progress(idx + 1)
        v = self.canvas.last_verdict
        if v is not None:
            color = {"GOOD": theme.GOOD, "WEAK": theme.WARN, "BAD": theme.BAD}[v.level]
            self.confirm.configure(text=v.summary(td.prompt), text_color=color)
        else:
            self.confirm.configure(text=f"✓ {td.prompt} saved", text_color=theme.GOOD)

    def _on_done(self):
        self._active = False
        s = self.app.session
        s.ended_at = time.time(); s.completed = True
        s.max_accl_channels = self.app.manager.max_accl_channels
        store.write_session_meta(s, self.app.selected_subject, self.app.selected_protocol.name)
        if syncer.is_configured():
            syncer.sync_in_background(lambda n: None)
        self._show_complete()

    def _show_complete(self):
        n = len(store.load_session_trials(self.app.session.id))
        self.strip.stop()
        c = self.canvas.canvas
        c.delete("all")
        w = c.winfo_width() or 900
        c.create_text(w//2, 160, text="✓ Session complete", fill=theme.GOOD,
                      font=(theme.FONT, 32, "bold"))
        c.create_text(w//2, 215, text=f"{n} trials saved · syncing to cloud",
                      fill=theme.TEXT, font=(theme.FONT, 16))
        self.canvas.set_decision_enabled(False)
        self.confirm.configure(text="")
        widgets.primary_button(self, "Done", lambda: self.app.navigate("home")).pack(pady=6)

    def _watchdog(self):
        if not self._active:
            return
        ready = self.app.device_ready()
        if self._was_ready and not ready:
            # Tap dropped mid-session — pause, don't record empties
            self._active = False
            if self.app.controller:
                self.app.controller.cancel()
            self.strip.stop()
            c = self.canvas.canvas
            c.delete("all")
            w = c.winfo_width() or 900
            c.create_text(w//2, 150, text="⚠ Tap disconnected",
                          fill=theme.BAD, font=(theme.FONT, 26, "bold"))
            c.create_text(w//2, 195, text="Reconnect the Tap and restart this session.",
                          fill=theme.TEXT, font=(theme.FONT, 14))
            self.canvas.set_decision_enabled(False)
            widgets.primary_button(self, "Back to Home",
                                   lambda: self.app.navigate("home")).pack(pady=6)
            return
        self._was_ready = ready
        self.after(500, self._watchdog)
