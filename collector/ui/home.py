"""Home / dashboard: device status, counts, primary actions."""
import customtkinter as ctk

from . import theme, widgets
from core import store
from sync import syncer


class HomeScreen(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app.container, fg_color=theme.BG)
        self.app = app
        widgets.header(self, "ASL Fingerspelling Collector")

        body = ctk.CTkFrame(self, fg_color=theme.BG)
        body.pack(fill="both", expand=True, padx=24)

        dev = widgets.card(body)
        dev.pack(fill="x", pady=8)
        ctk.CTkLabel(dev, text="Device", text_color=theme.TEXT,
                     font=(theme.FONT, 14, "bold")).pack(anchor="w", padx=16, pady=(12, 2))
        self.status = ctk.CTkLabel(dev, text="", text_color=theme.TEXT_MUTED,
                                   font=(theme.FONT_MONO, 12), justify="left")
        self.status.pack(anchor="w", padx=16, pady=(0, 12))

        self.counts = ctk.CTkLabel(body, text="", text_color=theme.TEXT,
                                   font=(theme.FONT, 13))
        self.counts.pack(anchor="w", pady=10)

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=8)
        widgets.secondary_button(btns, "Device", lambda: app.navigate("device"),
                                 width=130).pack(side="left", padx=6)
        widgets.secondary_button(btns, "Subjects", lambda: app.navigate("subjects"),
                                 width=130).pack(side="left", padx=6)
        widgets.secondary_button(btns, "Sessions", lambda: app.navigate("sessions"),
                                 width=130).pack(side="left", padx=6)

        self.start_btn = widgets.primary_button(
            body, "▶  Start New Session", lambda: app.navigate("session_setup"))
        self.start_btn.pack(pady=18)
        self.start_hint = ctk.CTkLabel(body, text="", text_color=theme.TEXT_MUTED,
                                       font=(theme.FONT, 11))
        self.start_hint.pack()

        self.sync_status = ctk.CTkLabel(body, text="", text_color=theme.TEXT_MUTED,
                                        font=(theme.FONT, 11))
        self.sync_status.pack(side="bottom", pady=8)

        self._tick()

    def on_show(self):
        self._refresh()
        if syncer.is_configured():
            self._pending_sync_n = None
            self.sync_status.configure(text="☁ syncing…")
            syncer.sync_in_background(self._on_sync_done)

    def _on_sync_done(self, n):
        self._pending_sync_n = n   # bg thread: plain attr only, no Tk

    def _refresh(self):
        subjects = store.load_subjects()
        sessions = store.list_sessions()
        self.counts.configure(text=f"{len(subjects)} subject(s)   ·   {len(sessions)} session(s)")
        ready = self.app.device_ready()
        if ready:
            self.status.configure(
                text=f"connected: {self.app.manager.device_name}\n"
                     f"max accl channels: {self.app.manager.max_accl_channels} (target 15)")
        elif self.app.ble_error:
            self.status.configure(text=self.app.ble_error)
        else:
            self.status.configure(text=f"bluetooth: {self.app.ble_state} — open Device to connect")
        can_start = ready and len(subjects) > 0
        self.start_btn.configure(state="normal" if can_start else "disabled")
        if not ready:
            self.start_hint.configure(text="Connect the Tap in Device first.")
        elif not subjects:
            self.start_hint.configure(text="Add a subject first.")
        else:
            self.start_hint.configure(text="")

    def _tick(self):
        self._refresh()
        n = getattr(self, "_pending_sync_n", None)
        if n is not None:
            self.sync_status.configure(text=f"☁ synced {n} session(s)" if n else "☁ up to date")
            self._pending_sync_n = None
        self.after(800, self._tick)
