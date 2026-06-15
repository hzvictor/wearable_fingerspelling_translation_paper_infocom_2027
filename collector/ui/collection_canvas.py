"""Active-collection canvas — tk.Canvas drawing inside a CTkFrame.

Renders banner + big word + per-letter highlight + ASL reference images, hosts the
Accept/Redo/Skip controls, and — the participant-feedback addition — computes a
GOOD/WEAK/BAD signal verdict from the controller's built-but-unsaved trial and
shows it in the DECIDE banner BEFORE the participant commits.

Implements the view interface CollectionController drives:
    render_prep / render_spelling / render_decide / set_decision_enabled
"""
from __future__ import annotations
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk

from core.paths import resource_path
from core.signal_quality import signal_quality
from . import theme

_REF_DIR = resource_path("assets", "asl_reference")
_REF_EXTS = (".gif", ".png", ".jpg", ".jpeg")
_REF_BOX = 130


class CollectionCanvas(ctk.CTkFrame):
    def __init__(self, master, controller_getter):
        super().__init__(master, fg_color=theme.BG)
        self._controller_getter = controller_getter
        self._img_cache: dict[str, ImageTk.PhotoImage] = {}
        self._ref_imgs: list[ImageTk.PhotoImage] = []
        self.last_verdict = None     # exposed for the post-accept confirmation

        self.canvas = tk.Canvas(self, bg=theme.BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", pady=(0, 14))
        self.btn_redo = ctk.CTkButton(btns, text="↻ Redo (R)", width=130,
                                      fg_color=theme.BG_CARD, hover_color="#22305a",
                                      command=lambda: self._fire("redo"))
        self.btn_skip = ctk.CTkButton(btns, text="✗ Skip (D)", width=130,
                                      fg_color=theme.BG_CARD, hover_color="#22305a",
                                      command=lambda: self._fire("skip"))
        self.btn_accept = ctk.CTkButton(btns, text="✓ Accept & Next  (Return)", width=260,
                                        fg_color=theme.ACCENT, hover_color="#c81e45",
                                        font=(theme.FONT, 14, "bold"),
                                        command=lambda: self._fire("accept"))
        self.btn_redo.pack(side="left", padx=12)
        self.btn_skip.pack(side="left", padx=12)
        self.btn_accept.pack(side="right", padx=12)
        self.set_decision_enabled(False)

    def bind_keys(self, toplevel):
        toplevel.bind("<Return>", lambda e: self._fire("accept"))
        toplevel.bind("r", lambda e: self._fire("redo"))
        toplevel.bind("d", lambda e: self._fire("skip"))

    def _fire(self, action):
        c = self._controller_getter()
        if not c or not self._decision_enabled:
            return
        getattr(c, action)()

    def set_decision_enabled(self, enabled: bool):
        self._decision_enabled = enabled
        state = "normal" if enabled else "disabled"
        for b in (self.btn_accept, self.btn_redo, self.btn_skip):
            b.configure(state=state)

    # ---- image loading ----

    def _load_ref(self, letter: str, size: int):
        key = f"{letter}@{size}"
        if key in self._img_cache:
            return self._img_cache[key]
        path = None
        for ext in _REF_EXTS:
            cand = _REF_DIR / f"{letter.upper()}{ext}"
            if cand.exists():
                path = cand
                break
        if path is None:
            return None
        try:
            img = Image.open(path).convert("RGB")
            img.thumbnail((size, size))
            photo = ImageTk.PhotoImage(img)
            self._img_cache[key] = photo
            return photo
        except Exception:
            return None

    # ---- view interface ----

    def render_prep(self, td, trial_num, total, countdown):
        self._paint(td, trial_num, total, theme.PREP_BANNER,
                   f"● GET READY · {countdown}", -1)

    def render_spelling(self, td, trial_num, total, highlight_idx, seconds_left):
        self._paint(td, trial_num, total, theme.SPELL_BANNER,
                   f"● SPELLING · {seconds_left:.1f}s", highlight_idx)

    def render_decide(self, td, trial_num, total):
        # compute the signal verdict on the built-but-unsaved trial
        verdict = None
        c = self._controller_getter()
        pending = getattr(c, "_pending_trial", None) if c else None
        if pending:
            verdict = signal_quality(pending.get("raw_data", []),
                                     pending.get("collect_time", td.collect_time()))
        self.last_verdict = verdict
        if verdict is None:
            color, text = theme.DONE_BANNER, "✓ DONE — Accept / Redo / Skip"
        else:
            color = {"GOOD": theme.DONE_BANNER, "WEAK": theme.WARN,
                     "BAD": theme.BAD}[verdict.level]
            text = verdict.decide_banner()
        self._paint(td, trial_num, total, color, text, -1)

    # ---- drawing (tk.Canvas) ----

    def _paint(self, td, trial_num, total, banner_color, banner_text, highlight_idx):
        c = self.canvas
        c.delete("all")
        self._ref_imgs.clear()
        w = c.winfo_width() or 900
        cx = w // 2

        c.create_text(cx, 22, text=f"Trial {trial_num} / {total}",
                      fill=theme.TEXT_MUTED, font=(theme.FONT, 13))
        c.create_rectangle(40, 44, w - 40, 92, fill=banner_color, outline="")
        c.create_text(cx, 68, text=banner_text, fill="white", font=(theme.FONT, 18, "bold"))
        c.create_text(cx, 150, text=td.prompt, fill=theme.ACCENT,
                      font=(theme.FONT_MONO, 60, "bold"))

        letters = td.letters or list(td.prompt)
        n = len(letters)
        spread = min(w - 120, n * 64)
        x0 = cx - spread // 2 + (spread // (2 * n) if n else 0)
        step = spread // n if n else 0
        for i, ch in enumerate(letters):
            active = (i == highlight_idx)
            c.create_text(x0 + i * step, 220, text=ch,
                          fill=theme.LETTER_ACTIVE if active else theme.LETTER_IDLE,
                          font=(theme.FONT_MONO, 30 if active else 22,
                                "bold" if active else "normal"))

        row_y = 320
        ref_spread = min(w - 100, n * (_REF_BOX + 16))
        rx0 = cx - ref_spread // 2
        rstep = ref_spread // n if n else 0
        for i, ch in enumerate(letters):
            active = (i == highlight_idx)
            size = int(_REF_BOX * (1.18 if active else 1.0))
            photo = self._load_ref(ch, size)
            ix = rx0 + i * rstep + rstep // 2
            if photo is not None:
                self._ref_imgs.append(photo)
                c.create_image(ix, row_y + 70, image=photo)
            else:
                c.create_text(ix, row_y + 70, text=ch, fill=theme.TEXT,
                              font=(theme.FONT_MONO, 40, "bold"))
            if active:
                half = size // 2 + 6
                c.create_rectangle(ix - half, row_y + 70 - half, ix + half, row_y + 70 + half,
                                   outline=theme.ACCENT, width=3)
        if n == 1 and td.hint:
            c.create_text(cx, row_y + 165, text=td.hint, fill=theme.TEXT_MUTED,
                          font=(theme.FONT, 12), width=w - 140)
