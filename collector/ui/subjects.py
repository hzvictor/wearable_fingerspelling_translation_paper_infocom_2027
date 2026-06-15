"""Subjects screen: list + add/edit (the user-centric core)."""
import time
import customtkinter as ctk

from . import theme, widgets
from core import store
from core.ids import next_subject_id
from core.models import Subject
from sync import syncer


class SubjectsScreen(ctk.CTkFrame):
    def __init__(self, app):
        super().__init__(app.container, fg_color=theme.BG)
        self.app = app
        widgets.header(self, "Subjects", back_command=lambda: app.navigate("home"))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=24)
        widgets.primary_button(bar, "+ Add subject", self._add, width=170).pack(side="left", pady=6)

        self.listframe = ctk.CTkScrollableFrame(self, fg_color=theme.BG_CARD,
                                                label_text="")
        self.listframe.pack(fill="both", expand=True, padx=24, pady=12)
        self._subjects = []

    def on_show(self):
        self._refresh()

    def _refresh(self):
        for w in self.listframe.winfo_children():
            w.destroy()
        self._subjects = store.load_subjects()
        if not self._subjects:
            ctk.CTkLabel(self.listframe, text="No subjects yet — click ‘+ Add subject’.",
                         text_color=theme.TEXT_MUTED, font=(theme.FONT, 13)).pack(pady=20)
            return
        for s in self._subjects:
            consent = "✓ consent" if s.consent_at else "no consent"
            row = ctk.CTkButton(
                self.listframe,
                text=f"{s.id}   {s.display_name}    {s.dominant_hand}-hand    {consent}",
                anchor="w", fg_color="transparent", hover_color="#22305a",
                text_color=theme.TEXT, font=(theme.FONT_MONO, 13), height=38,
                command=lambda sub=s: SubjectEditor(self, sub))
            row.pack(fill="x", pady=2, padx=4)

    def _add(self):
        SubjectEditor(self, None)

    def save(self, subject: Subject):
        store.save_subject(subject)
        syncer.sync_subject_in_background(subject.to_dict())
        self._refresh()


class SubjectEditor(ctk.CTkToplevel):
    def __init__(self, parent: SubjectsScreen, subject):
        super().__init__(parent, fg_color=theme.BG)
        self.parent = parent
        self.editing = subject
        self.title("Edit subject" if subject else "Add subject")
        self.geometry("420x420")

        existing_ids = [s.id for s in store.load_subjects()]
        self.v_id = ctk.StringVar(value=subject.id if subject else next_subject_id(existing_ids))
        self.v_name = ctk.StringVar(value=subject.display_name if subject else "")
        self.v_hand = ctk.StringVar(value=subject.dominant_hand if subject else "R")
        self.v_age = ctk.StringVar(value=subject.age_range if subject else "")
        self.v_consent = ctk.BooleanVar(value=bool(subject and subject.consent_at))

        pad = {"padx": 20, "pady": 6}
        self._row("Subject ID", ctk.CTkEntry(self, textvariable=self.v_id, width=140), pad)
        self._row("Display name", ctk.CTkEntry(self, textvariable=self.v_name, width=240), pad)
        hand = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkRadioButton(hand, text="Right", variable=self.v_hand, value="R").pack(side="left", padx=6)
        ctk.CTkRadioButton(hand, text="Left", variable=self.v_hand, value="L").pack(side="left", padx=6)
        self._row("Dominant hand", hand, pad)
        self._row("Age range", ctk.CTkEntry(self, textvariable=self.v_age, width=140), pad)
        ctk.CTkCheckBox(self, text="Consent captured", variable=self.v_consent).pack(anchor="w", padx=20, pady=8)
        self.err = ctk.CTkLabel(self, text="", text_color=theme.BAD, font=(theme.FONT, 11))
        self.err.pack()
        widgets.primary_button(self, "Save", self._save, width=120).pack(pady=10)

    def _row(self, label, widget, pad):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="x", **pad)
        ctk.CTkLabel(f, text=label, width=120, anchor="w",
                     text_color=theme.TEXT_MUTED).pack(side="left")
        widget.pack(in_=f, side="left")

    def _save(self):
        sid = self.v_id.get().strip()
        name = self.v_name.get().strip()
        if not sid or not name:
            self.err.configure(text="ID and name are required.")
            return
        s = self.editing or Subject(id=sid, display_name=name)
        s.id, s.display_name = sid, name
        s.dominant_hand = self.v_hand.get()
        s.age_range = self.v_age.get().strip()
        if self.v_consent.get() and not s.consent_at:
            s.consent_at = time.time()
        if not self.v_consent.get():
            s.consent_at = None
        self.parent.save(s)
        self.destroy()
