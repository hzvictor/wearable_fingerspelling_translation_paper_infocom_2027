"""Local-first JSON store (source of truth) in ~/Library/Application Support/ASLCollector/.

Layout:
    subjects.json                       all subjects (one small file)
    sessions/{session_id}/meta.json     denormalized session metadata
    sessions/{session_id}/trial_NNN.json one file per accepted trial (atomic)

All writes are atomic (.tmp + os.replace). The trial JSON uses the unified
word-shaped schema (gestures = 1-letter words) so it stays compatible with
finger/tapstrap/prepare_finetune_data.py.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path

from .paths import subjects_path, session_root, sessions_dir
from .models import Subject, Session


# ---------------------------------------------------------------------------
# atomic write
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------

def load_subjects() -> list[Subject]:
    p = subjects_path()
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [Subject(**s) for s in data]


def save_subject(subject: Subject) -> None:
    subjects = load_subjects()
    now = time.time()
    subject.updated_at = now
    found = False
    for i, s in enumerate(subjects):
        if s.id == subject.id:
            if not subject.created_at:
                subject.created_at = s.created_at
            subjects[i] = subject
            found = True
            break
    if not found:
        if not subject.created_at:
            subject.created_at = now
        subjects.append(subject)
    _atomic_write_json(subjects_path(), [s.to_dict() for s in subjects])


def get_subject(subject_id: str) -> Subject | None:
    for s in load_subjects():
        if s.id == subject_id:
            return s
    return None


# ---------------------------------------------------------------------------
# Sessions + trials
# ---------------------------------------------------------------------------

def existing_session_ids() -> set[str]:
    d = sessions_dir()
    return {p.name for p in d.iterdir() if p.is_dir()} if d.exists() else set()


def write_session_meta(session: Session, subject: Subject, protocol_name: str) -> None:
    meta = {
        "session_id": session.id,
        "subject_id": session.subject_id,
        "subject_name": subject.display_name if subject else "",
        "subject_dominant_hand": subject.dominant_hand if subject else "",
        "protocol_id": session.protocol_id,
        "protocol_name": protocol_name,
        "device_name": session.device_name,
        "device_uuid": session.device_uuid,
        "max_accl_channels": session.max_accl_channels,
        "target_trials": session.target_trials,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "completed": session.completed,
    }
    _atomic_write_json(session_root(session.id) / "meta.json", meta)


def next_trial_index(session_id: str) -> int:
    root = session_root(session_id)
    n = len(list(root.glob("trial_*.json")))
    return n + 1


def write_trial(session_id: str, trial: dict) -> Path:
    """Write one trial atomically as trial_NNN.json. `trial` is the unified
    word-shaped dict (see collection_controller.build_trial). Returns the path."""
    idx = trial.get("trial") or next_trial_index(session_id)
    path = session_root(session_id) / f"trial_{idx:03d}.json"
    _atomic_write_json(path, trial)
    return path


def load_session_meta(session_id: str) -> dict | None:
    p = session_root(session_id) / "meta.json"
    return json.loads(p.read_text()) if p.exists() else None


def load_session_trials(session_id: str) -> list[dict]:
    root = session_root(session_id)
    out = []
    for p in sorted(root.glob("trial_*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except Exception:
            pass
    return out


def list_sessions() -> list[dict]:
    """All sessions' meta (newest first)."""
    out = []
    for sid in sorted(existing_session_ids(), reverse=True):
        meta = load_session_meta(sid)
        if meta:
            out.append(meta)
    return out
