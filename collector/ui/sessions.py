"""Sessions list + per-session review (trial summary)."""
import customtkinter as ctk

from . import theme, widgets
from core import store


class SessionsScreen(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app.container, fg_color=theme.BG)
        self.app = app
        widgets.header(self, "Sessions", back_command=lambda: app.navigate("home"))

        self.listframe = ctk.CTkScrollableFrame(self, fg_color=theme.BG_CARD, height=180)
        self.listframe.pack(fill="x", padx=24, pady=(8, 6))

        self.detail = ctk.CTkTextbox(self, fg_color=theme.BG_CARD, text_color=theme.TEXT,
                                     font=(theme.FONT_MONO, 11), wrap="none")
        self.detail.pack(fill="both", expand=True, padx=24, pady=(6, 16))
        self._metas = []

    def on_show(self, focus_session=None):
        for w in self.listframe.winfo_children():
            w.destroy()
        self._metas = store.list_sessions()
        if not self._metas:
            ctk.CTkLabel(self.listframe, text="No sessions yet.",
                         text_color=theme.TEXT_MUTED).pack(pady=14)
        for m in self._metas:
            ctk.CTkButton(
                self.listframe, anchor="w", fg_color="transparent",
                hover_color="#22305a", text_color=theme.TEXT, font=(theme.FONT_MONO, 12),
                height=34,
                text=(f"{m['session_id']}  {m.get('subject_id',''):6s} "
                      f"{m.get('protocol_name',''):22s} ch={m.get('max_accl_channels','?')} "
                      f"{m.get('target_trials','?')} trials"),
                command=lambda mm=m: self._render_detail(mm)).pack(fill="x", pady=1, padx=4)
        self.detail.delete("1.0", "end")
        if focus_session:
            for m in self._metas:
                if m["session_id"] == focus_session:
                    self._render_detail(m)
                    break

    def _render_detail(self, meta):
        sid = meta["session_id"]
        trials = store.load_session_trials(sid)
        self.detail.delete("1.0", "end")
        names = ["thumb", "index", "middle", "ring", "pinky"]
        lines = [
            f"session  {sid}",
            f"subject  {meta.get('subject_id')}  ({meta.get('subject_name','')})",
            f"protocol {meta.get('protocol_name')}",
            f"device   {meta.get('device_name')}   max accl channels {meta.get('max_accl_channels')}",
            f"trials   {len(trials)}",
            "",
        ]
        for t in trials:
            raw = t.get("raw_data", [])
            ch = max((len(m.get("payload", [])) for m in raw if m.get("type") == "accl"), default=0)
            fingers = set()
            for m in raw:
                if m.get("type") == "accl":
                    pl = m["payload"]
                    for i in range(min(5, len(pl)//3)):
                        if any(pl[i*3:i*3+3]):
                            fingers.add(i)
            fstr = "".join(n[0] for i, n in enumerate(names) if i in fingers)
            lines.append(f"  #{t.get('trial'):>2}  {t.get('word',''):10s} ch={ch:2d}  "
                         f"accl={t.get('num_accl',0):4d} imu={t.get('num_imu',0):4d} fingers={fstr}")
        self.detail.insert("1.0", "\n".join(lines))
