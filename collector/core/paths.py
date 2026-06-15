"""Filesystem paths — resolve bundled resources vs the writable data directory.

In a PyInstaller .app, the code/assets live read-only inside the bundle
(sys._MEIPASS), while all user data (sessions, config, sync manifest) must go to
~/Library/Application Support/ASLCollector/. In dev (running from source), assets
live next to the package and data goes to the same Application Support dir so dev
and packaged behave identically.
"""
import os
import sys
from pathlib import Path

APP_NAME = "ASLCollector"


def resource_path(*parts) -> Path:
    """Path to a bundled, read-only resource (assets, builtin protocols)."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        # collector/core/paths.py -> collector/
        base = Path(__file__).resolve().parent.parent
    return base.joinpath(*parts)


def app_support_dir() -> Path:
    """Writable per-user data directory. Created if missing."""
    d = Path.home() / "Library" / "Application Support" / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def sessions_dir() -> Path:
    d = app_support_dir() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return app_support_dir() / "firebase_config.json"


def subjects_path() -> Path:
    return app_support_dir() / "subjects.json"


def manifest_path() -> Path:
    return app_support_dir() / ".synced.json"


def session_root(session_id: str) -> Path:
    d = sessions_dir() / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d
