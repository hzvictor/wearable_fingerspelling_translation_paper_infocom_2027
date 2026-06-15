"""Minimal frame-stack router: register named screen factories, show one at a time."""
import tkinter as tk

from . import theme


class Router:
    def __init__(self, container: tk.Frame):
        self.container = container
        self._factories = {}   # name -> callable(app, parent) -> Frame
        self._frames = {}      # name -> Frame instance (lazily built)
        self.current = None

    def register(self, name, factory):
        self._factories[name] = factory

    def show(self, name, **kwargs):
        if self.current is not None:
            self._frames[self.current].pack_forget()
        frame = self._frames.get(name)
        if frame is None:
            frame = self._factories[name]()
            self._frames[name] = frame
        frame.pack(fill="both", expand=True)
        self.current = name
        # let a screen refresh its data each time it's shown
        if hasattr(frame, "on_show"):
            frame.on_show(**kwargs)
        return frame
