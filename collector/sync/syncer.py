"""Post-session sync trigger. Runs the (blocking) urllib uploads on a daemon
thread so the Tk/BLE main thread never stalls. Network threads are safe — only
CoreBluetooth and Tk must stay on the main thread.

Local JSON is always the source of truth; sync is best-effort and idempotent, so
a failed upload simply retries on the next trigger.
"""
from __future__ import annotations
import threading

from . import firebase


def is_configured() -> bool:
    return firebase.load_config() is not None


def sync_in_background(on_done=lambda n: None):
    """Fire-and-forget sync of all pending sessions."""
    def _run():
        try:
            n = firebase.sync_all()
        except Exception:
            n = 0
        on_done(n)
    threading.Thread(target=_run, daemon=True).start()


def sync_subject_in_background(subject_dict: dict):
    def _run():
        cfg = firebase.load_config()
        if cfg:
            try:
                firebase.sync_subject(cfg, subject_dict)
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()
