"""Load + validate protocols.

Builtin protocols are bundled JSON (protocols/builtin/*.json, generated once from
the old WORD_LIST/GESTURES). Custom protocols live in the writable app-support dir
(future). Returns core.models.Protocol objects.
"""
from __future__ import annotations
import json

from core.paths import resource_path, app_support_dir
from core.models import Protocol, TrialDef

BUILTIN_ORDER = ["asl_alphabet", "asl_digits", "confusion_words", "all_words"]


def _protocol_from_dict(d: dict) -> Protocol:
    trials = [
        TrialDef(
            prompt=t["prompt"],
            letters=t.get("letters", list(t["prompt"])),
            group=t.get("group", ""),
            hint=t.get("hint", ""),
            confusion_test=t.get("confusion_test"),
            duration_ms=t.get("duration_ms", 0),
        )
        for t in d.get("trials", [])
    ]
    return Protocol(
        id=d["id"], name=d["name"], type=d["type"],
        builtin=d.get("builtin", True), description=d.get("description", ""),
        trials=trials,
    )


def load_builtin_protocols() -> list[Protocol]:
    out = []
    builtin_dir = resource_path("protocols", "builtin")
    for pid in BUILTIN_ORDER:
        p = builtin_dir / f"{pid}.json"
        if p.exists():
            out.append(_protocol_from_dict(json.loads(p.read_text())))
    return out


def load_custom_protocols() -> list[Protocol]:
    out = []
    custom_dir = app_support_dir() / "protocols"
    if custom_dir.exists():
        for p in sorted(custom_dir.glob("*.json")):
            try:
                out.append(_protocol_from_dict(json.loads(p.read_text())))
            except Exception:
                pass
    return out


def load_all_protocols() -> list[Protocol]:
    return load_builtin_protocols() + load_custom_protocols()


def get_protocol(protocol_id: str) -> Protocol | None:
    for p in load_all_protocols():
        if p.id == protocol_id:
            return p
    return None
