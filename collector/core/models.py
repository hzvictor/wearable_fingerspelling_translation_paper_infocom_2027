"""Data models — user-centric, mirroring docs/product_spec.md (simplified for Mac).

Subject -> Session -> Trial, plus Protocol (word/gesture lists of TrialDef).
Dataclasses are JSON-serializable via asdict(); the store layer handles disk I/O.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Subject:
    id: str                      # "S001" (user-editable)
    display_name: str
    dominant_hand: str = "R"     # "L" | "R"
    age_range: str = ""
    gender: str = ""
    notes: str = ""
    consent_at: Optional[float] = None   # unix seconds when consent captured
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class TrialDef:
    """One prompt in a protocol (a word or a single-letter gesture)."""
    prompt: str                          # "CAT" or "A"
    letters: list[str] = field(default_factory=list)   # ["C","A","T"] or ["A"]
    group: str = ""                      # "confusion" | "alpha1" | "digits" | ...
    hint: str = ""                       # tooltip, e.g. "Fist with thumb on side"
    confusion_test: Optional[str] = None
    duration_ms: int = 0                 # 0 => compute default from letters

    def collect_time(self) -> float:
        if self.duration_ms > 0:
            return self.duration_ms / 1000.0
        # default: 1s/letter + 1s buffer, min 3s (collect_words.get_collect_time)
        return max(3.0, len(self.letters) * 1.0 + 1.0)

    def to_dict(self):
        return asdict(self)


@dataclass
class Protocol:
    id: str                      # "confusion_words", "asl_alphabet"
    name: str
    type: str                    # "word" | "gesture"
    builtin: bool = True
    description: str = ""
    trials: list[TrialDef] = field(default_factory=list)

    def groups(self) -> list[str]:
        seen = []
        for t in self.trials:
            if t.group and t.group not in seen:
                seen.append(t.group)
        return seen

    def to_dict(self):
        d = asdict(self)
        return d


@dataclass
class Session:
    id: str                      # "20260530_142312"
    subject_id: str
    protocol_id: str
    device_name: str = ""
    device_uuid: str = ""
    max_accl_channels: int = 0
    target_trials: int = 0
    started_at: float = 0.0
    ended_at: Optional[float] = None
    completed: bool = False

    def to_dict(self):
        return asdict(self)
