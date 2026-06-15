"""Audio cues — ported from collect_gestures.py (say/beep*).

All non-blocking (subprocess.Popen, not run) so they never stall the Tk/BLE loop.
Uses macOS system binaries (/usr/bin/say, /usr/bin/afplay) present on every Mac.
"""
import subprocess

_SOUND = {
    "tick": "/System/Library/Sounds/Tink.aiff",
    "start": "/System/Library/Sounds/Pop.aiff",
    "done": "/System/Library/Sounds/Glass.aiff",
}


def say(text: str) -> None:
    try:
        subprocess.Popen(["say", "-v", "Samantha", text])
    except Exception:
        pass


def _play(key: str) -> None:
    try:
        subprocess.Popen(["afplay", _SOUND[key]])
    except Exception:
        pass


def beep():       _play("tick")
def beep_start(): _play("start")
def beep_done():  _play("done")
