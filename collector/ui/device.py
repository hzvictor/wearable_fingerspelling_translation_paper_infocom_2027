"""Device screen: connection state, MTU/channel metrics, live finger strip, test."""
import customtkinter as ctk

from . import theme, widgets
from .signal_strip import FingerActivityStrip
from core.signal_quality import signal_quality
import config


class DeviceScreen(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app.container, fg_color=theme.BG)
        self.app = app
        widgets.header(self, "Device", back_command=lambda: app.navigate("home"))

        body = ctk.CTkFrame(self, fg_color=theme.BG)
        body.pack(fill="both", expand=True, padx=24)

        self.state_lbl = ctk.CTkLabel(body, text="", text_color=theme.ACCENT,
                                      font=(theme.FONT, 16, "bold"))
        self.state_lbl.pack(anchor="w", pady=(8, 12))

        metrics = widgets.card(body)
        metrics.pack(fill="x")
        self.metrics_lbl = ctk.CTkLabel(metrics, text="", text_color=theme.TEXT,
                                        font=(theme.FONT_MONO, 13), justify="left")
        self.metrics_lbl.pack(anchor="w", padx=16, pady=12)

        # live finger strip — always animating from manager.recent
        self.strip = FingerActivityStrip(body, app.manager,
                                         label="LIVE — move all five fingers to verify")
        self.strip.pack(pady=12)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        widgets.secondary_button(row, "↻ Reconnect", app.reconnect, width=140).pack(side="left", padx=4)
        widgets.secondary_button(row, "Test signal (2 s)", self._test_signal, width=160).pack(side="left", padx=4)
        self.test_result = ctk.CTkLabel(body, text="", text_color=theme.TEXT,
                                        font=(theme.FONT, 13))
        self.test_result.pack(anchor="w", pady=8)

        ctk.CTkLabel(body, text=(
            "The Tap must be connected to this Mac as a keyboard (System Settings ▸ "
            "Bluetooth) and TapManager Developer Mode must be ON for the full "
            "15-channel stream. Tap all five fingers — each dot should light green."),
            text_color=theme.TEXT_MUTED, font=(theme.FONT, 11), justify="left",
            wraplength=560).pack(anchor="w", pady=8)

        self._tick()

    def on_show(self):
        self.strip.start()
        self._refresh()

    def _test_signal(self):
        """2 s window: snapshot recent buffer, verdict on finger coverage."""
        self.test_result.configure(text="testing… move all five fingers", text_color=theme.WARN)
        # clear stale recent so the test reflects the next 2 s
        self.app.manager.recent.clear()
        self.after(2000, self._test_done)

    def _test_done(self):
        snap = list(self.app.manager.recent)
        v = signal_quality(snap, collect_time=2.0)
        color = {"GOOD": theme.GOOD, "WEAK": theme.WARN, "BAD": theme.BAD}[v.level]
        if v.level == "GOOD":
            msg = f"✓ all 5 fingers detected · {v.packets_per_sec:.0f} frames/s · {v.max_accl_channels}ch"
        else:
            why = v.reasons[0] if v.reasons else v.level
            msg = f"{v.level}: {v.n_fingers}/5 fingers — {why}"
        self.test_result.configure(text=msg, text_color=color)

    def _refresh(self):
        m = self.app.manager
        if self.app.device_ready():
            self.state_lbl.configure(text=f"READY ✓  ({m.device_name})")
        elif self.app.ble_error:
            self.state_lbl.configure(text=f"⚠ {self.app.ble_error}")
        else:
            self.state_lbl.configure(text=f"bluetooth: {self.app.ble_state}")
        accl = sum(1 for x in m.recent if x["type"] == "accl")
        imu = sum(1 for x in m.recent if x["type"] == "imu")
        ok = "✓" if m.max_accl_channels >= config.TARGET_ACCL_CHANNELS else "—"
        self.metrics_lbl.configure(text=(
            f"max accl channels : {m.max_accl_channels}  {ok}  (target {config.TARGET_ACCL_CHANNELS})\n"
            f"recent frames      : {accl} accl / {imu} imu"))

    def _tick(self):
        self._refresh()
        self.after(300, self._tick)
