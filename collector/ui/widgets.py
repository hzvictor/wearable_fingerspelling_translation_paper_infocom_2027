"""Reusable CustomTkinter widgets in the app's dark theme."""
import customtkinter as ctk

from . import theme


def header(parent, title, back_command=None):
    bar = ctk.CTkFrame(parent, fg_color="transparent")
    bar.pack(fill="x", pady=(16, 8), padx=16)
    if back_command:
        ctk.CTkButton(bar, text="‹ Back", width=70, command=back_command,
                      fg_color=theme.BG_CARD, hover_color="#22305a").pack(side="left")
    ctk.CTkLabel(bar, text=title, text_color=theme.TEXT,
                 font=(theme.FONT, 22, "bold")).pack(side="left", padx=12)
    return bar


def primary_button(parent, text, command, **kw):
    return ctk.CTkButton(parent, text=text, command=command,
                         fg_color=theme.ACCENT, hover_color="#c81e45",
                         text_color="white", font=(theme.FONT, 15, "bold"),
                         height=44, corner_radius=10, **kw)


def secondary_button(parent, text, command, **kw):
    return ctk.CTkButton(parent, text=text, command=command,
                         fg_color=theme.BG_CARD, hover_color="#22305a",
                         text_color=theme.TEXT, font=(theme.FONT, 13),
                         height=40, corner_radius=10, **kw)


def card(parent):
    return ctk.CTkFrame(parent, fg_color=theme.BG_CARD, corner_radius=12)


def label(parent, text, muted=False, big=False, **kw):
    return ctk.CTkLabel(parent, text=text,
                        text_color=theme.TEXT_MUTED if muted else theme.TEXT,
                        font=(theme.FONT, 16 if big else 12,
                              "bold" if big else "normal"), **kw)


def empty_state(parent, title, body, cta=None, on_cta=None):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(f, text=title, text_color=theme.TEXT,
                 font=(theme.FONT, 16, "bold")).pack(pady=(40, 8))
    ctk.CTkLabel(f, text=body, text_color=theme.TEXT_MUTED,
                 font=(theme.FONT, 12), wraplength=420, justify="center").pack(pady=4)
    if cta and on_cta:
        primary_button(f, cta, on_cta).pack(pady=16)
    return f
