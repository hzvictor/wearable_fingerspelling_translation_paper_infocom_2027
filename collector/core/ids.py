"""ID generation: session IDs and subject IDs.

session_id format matches the Mac/Android pipeline: "%Y%m%d_%H%M%S" (greppable,
human-readable). A 4-char random suffix is appended only on same-second collision.
"""
from __future__ import annotations
import random
import string
from datetime import datetime


def new_session_id(existing: set[str] | None = None) -> str:
    base = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not existing or base not in existing:
        return base
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{base}_{suffix}"


def next_subject_id(existing_ids) -> str:
    """Auto-suggest S001, S002, ... (user-editable). Skips taken numbers."""
    taken = set()
    for sid in existing_ids:
        if sid and sid[0] in ("S", "s") and sid[1:].isdigit():
            taken.add(int(sid[1:]))
    n = 1
    while n in taken:
        n += 1
    return f"S{n:03d}"
