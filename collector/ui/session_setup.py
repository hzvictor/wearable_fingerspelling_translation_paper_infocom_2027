"""Session setup: pick subject + protocol + group subset, then launch collection."""
import time
import customtkinter as ctk

from . import theme, widgets
from core import store
from core.ids import new_session_id
from core.models import Session
from protocols.loader import load_all_protocols


class SessionSetupScreen(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app.container, fg_color=theme.BG)
        self.app = app
        widgets.header(self, "Start Session", back_command=lambda: app.navigate("home"))
        body = ctk.CTkFrame(self, fg_color=theme.BG)
        body.pack(fill="both", expand=True, padx=24)

        self.v_subject = ctk.StringVar(value="")
        self.v_protocol = ctk.StringVar(value="")

        srow = ctk.CTkFrame(body, fg_color="transparent"); srow.pack(fill="x", pady=6)
        ctk.CTkLabel(srow, text="Subject", width=90, anchor="w",
                     text_color=theme.TEXT_MUTED).pack(side="left")
        self.subject_menu = ctk.CTkOptionMenu(srow, variable=self.v_subject, values=[""],
                                              width=320, command=lambda *_: self._update_summary())
        self.subject_menu.pack(side="left")

        prow = ctk.CTkFrame(body, fg_color="transparent"); prow.pack(fill="x", pady=6)
        ctk.CTkLabel(prow, text="Protocol", width=90, anchor="w",
                     text_color=theme.TEXT_MUTED).pack(side="left")
        self.protocol_menu = ctk.CTkOptionMenu(prow, variable=self.v_protocol, values=[""],
                                              width=320, command=lambda *_: self._on_protocol())
        self.protocol_menu.pack(side="left")

        ctk.CTkLabel(body, text="Groups", text_color=theme.TEXT_MUTED).pack(anchor="w", pady=(12, 2))
        self.groups_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.groups_frame.pack(fill="x")
        self.group_vars = {}

        self.summary = ctk.CTkLabel(body, text="", text_color=theme.TEXT,
                                    font=(theme.FONT, 13))
        self.summary.pack(anchor="w", pady=14)
        self.start_btn = widgets.primary_button(body, "▶  Start", self._start, width=160)
        self.start_btn.pack(anchor="w")
        self.err = ctk.CTkLabel(body, text="", text_color=theme.BAD, font=(theme.FONT, 11))
        self.err.pack(anchor="w", pady=6)

    def on_show(self):
        self.err.configure(text="")
        subjects = store.load_subjects()
        self._subjects = {f"{s.id}  {s.display_name}": s for s in subjects}
        self._protocols = {f"{p.name}  ({len(p.trials)})": p for p in load_all_protocols()}
        subj_opts = list(self._subjects) or [""]
        proto_opts = list(self._protocols) or [""]
        self.subject_menu.configure(values=subj_opts)
        self.protocol_menu.configure(values=proto_opts)
        # preselect
        cur_subj = subj_opts[0]
        if self.app.selected_subject:
            for k, s in self._subjects.items():
                if s.id == self.app.selected_subject.id:
                    cur_subj = k
        self.v_subject.set(cur_subj)
        self.v_protocol.set(proto_opts[0])
        self._on_protocol()

    def _on_protocol(self):
        for w in self.groups_frame.winfo_children():
            w.destroy()
        self.group_vars = {}
        proto = self._protocols.get(self.v_protocol.get())
        if proto:
            for g in proto.groups():
                v = ctk.BooleanVar(value=True)
                self.group_vars[g] = v
                cnt = sum(1 for t in proto.trials if t.group == g)
                ctk.CTkCheckBox(self.groups_frame, text=f"{g} ({cnt})", variable=v,
                                command=self._update_summary,
                                checkbox_width=20, checkbox_height=20).pack(side="left", padx=6)
        self._update_summary()

    def _selected_trials(self):
        proto = self._protocols.get(self.v_protocol.get())
        if not proto:
            return None, []
        chosen = {g for g, v in self.group_vars.items() if v.get()}
        if self.group_vars and chosen != set(self.group_vars):
            trials = [t for t in proto.trials if t.group in chosen]
        else:
            trials = list(proto.trials)
        return proto, trials

    def _update_summary(self):
        proto, trials = self._selected_trials()
        if proto:
            est = sum(t.collect_time() + 3 for t in trials)
            self.summary.configure(text=f"{len(trials)} trials  ·  ~{est/60:.1f} min")

    def _start(self):
        subj = self._subjects.get(self.v_subject.get())
        proto, trials = self._selected_trials()
        if not subj:
            self.err.configure(text="Pick a subject."); return
        if not proto or not trials:
            self.err.configure(text="Pick a protocol with at least one group."); return
        if not self.app.device_ready():
            self.err.configure(text="Tap not ready — connect it in Device."); return

        sid = new_session_id(store.existing_session_ids())
        session = Session(
            id=sid, subject_id=subj.id, protocol_id=proto.id,
            device_name=self.app.manager.device_name or "",
            device_uuid=self.app.manager.device_uuid or "",
            target_trials=len(trials), started_at=time.time(), completed=False)
        store.write_session_meta(session, subj, proto.name)

        self.app.selected_subject = subj
        self.app.selected_protocol = proto
        self.app.session = session
        self.app.session_trials = trials
        self.app.navigate("collection")
