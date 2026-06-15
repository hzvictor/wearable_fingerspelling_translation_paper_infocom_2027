"""FingerActivityStrip — the live "is my hand being recorded?" indicator.

Five labeled dots (thumb…pinky) that light green when that finger moves. Reads
from manager.recent (the always-updated deque, manager.py), redraws at 10 Hz via
self.after — well inside the RunLoopPump's 15 ms cadence. Recolors 5 canvas items
per tick (no allocation), so it's cheap and never stutters.

This directly surfaces the #1 data defect (a silent finger = loose strap), and is
consistent with the GOOD/WEAK/BAD verdict which is finger-coverage driven.
"""
from __future__ import annotations
import tkinter as tk

import customtkinter as ctk

from . import theme

FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
_DEADBAND = 3          # raw accel units; above this = "moving"
_WINDOW = 30           # frames of history scanned each tick
_TICK_MS = 100         # 10 Hz


class FingerActivityStrip(ctk.CTkFrame):
    def __init__(self, master, manager, dot=26, label="LIVE — move your fingers"):
        super().__init__(master, fg_color=theme.BG_CARD)
        self.manager = manager
        self.dot = dot
        self.active_fingers: set[int] = set()   # exposed for tests
        self._running = False

        ctk.CTkLabel(self, text=label, text_color=theme.TEXT_MUTED,
                     font=(theme.FONT, 11)).pack(pady=(8, 2))
        w = len(FINGERS) * (dot + 34)
        self.canvas = tk.Canvas(self, width=w, height=dot + 34,
                                bg=theme.BG_CARD, highlightthickness=0)
        self.canvas.pack(padx=10, pady=(0, 8))
        self._dots = []
        self._labels = []
        for i, name in enumerate(FINGERS):
            cx = 28 + i * (dot + 34)
            cy = dot // 2 + 4
            o = self.canvas.create_oval(cx - dot//2, cy - dot//2, cx + dot//2, cy + dot//2,
                                        fill=theme.LETTER_IDLE, outline="")
            t = self.canvas.create_text(cx, cy + dot//2 + 12, text=name,
                                        fill=theme.TEXT_MUTED, font=(theme.FONT, 9))
            self._dots.append(o)
            self._labels.append(t)

    def start(self):
        if not self._running:
            self._running = True
            self._tick()

    def stop(self):
        self._running = False

    def destroy(self):
        self._running = False
        super().destroy()

    def compute_active(self) -> set[int]:
        """Active fingers from the last _WINDOW accl frames of manager.recent.
        Pure (no Tk) so tests can call it directly."""
        recent = list(getattr(self.manager, "recent", []))
        accl = [m for m in recent if m.get("type") == "accl"][-_WINDOW:]
        active = set()
        for m in accl:
            pl = m.get("payload", [])
            for i in range(min(5, len(pl) // 3)):
                if max(abs(v) for v in pl[i*3:i*3+3]) > _DEADBAND:
                    active.add(i)
        return active

    def refresh(self):
        """Recompute + recolor once (also callable from tests)."""
        self.active_fingers = self.compute_active()
        for i, o in enumerate(self._dots):
            on = i in self.active_fingers
            self.canvas.itemconfig(o, fill=theme.GOOD if on else theme.LETTER_IDLE)
            self.canvas.itemconfig(self._labels[i],
                                   fill=theme.TEXT if on else theme.TEXT_MUTED)

    def _tick(self):
        if not self._running:
            return
        try:
            self.refresh()
        except tk.TclError:
            return   # widget destroyed
        self.after(_TICK_MS, self._tick)
