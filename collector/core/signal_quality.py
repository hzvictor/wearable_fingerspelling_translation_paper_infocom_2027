"""Signal-quality verdict for a collected trial — the heart of participant feedback.

Single source of truth for "did this trial actually record well?". Used both
post-trial (gate the DECIDE step) and for the Device "Test signal" check. Replaces
the duplicated finger-detection snippets in ui/device.py and ui/sessions.py.

Thresholds are fractions of the expected rate because a trial's collect_time
varies (max(3.0, n_letters+1)). At ~190 Hz a 4 s trial should yield ~760 accl
frames; dropping below 70% means real BLE packet loss, below 40% means the link
briefly died. All five fingers should move during fingerspelling — a silent
finger almost always means a loose strap sensor, the #1 real defect.
"""
from __future__ import annotations
from dataclasses import dataclass, field

FINGER_NAMES = ["thumb", "index", "middle", "ring", "pinky"]

GOOD, WEAK, BAD = "GOOD", "WEAK", "BAD"
_ORDER = {GOOD: 0, WEAK: 1, BAD: 2}

# rate thresholds (fraction of expected_hz)
RATE_GOOD = 0.70
RATE_WEAK = 0.40
# absolute floor of accl frames below which the trial is unusable regardless
MIN_ACCL_FRAMES = 30


@dataclass
class Verdict:
    level: str                       # GOOD | WEAK | BAD
    reasons: list[str] = field(default_factory=list)
    packets_per_sec: float = 0.0
    n_accl: int = 0
    n_imu: int = 0
    fingers: list[str] = field(default_factory=list)
    n_fingers: int = 0
    max_accl_channels: int = 0

    @property
    def is_good(self) -> bool:
        return self.level == GOOD

    def summary(self, word: str = "") -> str:
        """Short confirmation copy for the participant."""
        w = f"{word} " if word else ""
        if self.level == GOOD:
            return (f"✓ {w}saved · {self.n_accl} frames · "
                    f"{self.n_fingers} fingers · {self.max_accl_channels}ch")
        if self.level == WEAK:
            why = self.reasons[0] if self.reasons else "weak signal"
            return f"⚠ {w}saved but weak — {why}"
        why = self.reasons[0] if self.reasons else "bad signal"
        return f"⚠ {w}looks bad — {why}. Please redo."

    def decide_banner(self) -> str:
        """Banner shown at the DECIDE step, BEFORE the participant commits."""
        if self.level == GOOD:
            return "✓ Good capture — Accept"
        if self.level == WEAK:
            why = self.reasons[0] if self.reasons else "weak"
            return f"⚠ {why} — consider Redo"
        why = self.reasons[0] if self.reasons else "bad"
        return f"⚠ {why} — please Redo"


def _worst(a: str, b: str) -> str:
    return a if _ORDER[a] >= _ORDER[b] else b


def fingers_with_motion(raw_buffer) -> set[int]:
    """Finger indices (0..4) with any non-zero XYZ anywhere in the buffer."""
    moved = set()
    for m in raw_buffer:
        if m.get("type") != "accl":
            continue
        pl = m.get("payload", [])
        for i in range(min(5, len(pl) // 3)):
            if any(pl[i * 3:i * 3 + 3]):
                moved.add(i)
    return moved


def signal_quality(raw_buffer, collect_time: float,
                   expected_hz: float = 190.0, target_channels: int = 15) -> Verdict:
    accl = [m for m in raw_buffer if m.get("type") == "accl"]
    imu = [m for m in raw_buffer if m.get("type") == "imu"]
    n_accl, n_imu = len(accl), len(imu)
    ct = max(0.1, float(collect_time))
    pps = n_accl / ct
    max_ch = max((len(m.get("payload", [])) for m in accl), default=0)
    moved = fingers_with_motion(raw_buffer)
    finger_names = [FINGER_NAMES[i] for i in sorted(moved)]

    level = GOOD
    reasons: list[str] = []

    # absolute floor (mid-trial disconnect)
    if n_accl < MIN_ACCL_FRAMES:
        level = BAD
        reasons.append(f"only {n_accl} frames captured")

    # rate
    if pps < RATE_WEAK * expected_hz:
        level = _worst(level, BAD)
        reasons.append(f"only {pps:.0f} frames/s (expected ~{expected_hz:.0f})")
    elif pps < RATE_GOOD * expected_hz:
        level = _worst(level, WEAK)
        reasons.append(f"{pps:.0f} frames/s (expected ~{expected_hz:.0f})")

    # finger coverage
    silent = [FINGER_NAMES[i] for i in range(5) if i not in moved]
    if len(moved) <= 2:
        level = _worst(level, BAD)
        reasons.append(f"only {len(moved)} finger(s) moved")
    elif len(moved) < 5:
        level = _worst(level, WEAK)
        reasons.append(f"{','.join(silent)} barely moved")

    # channel count (Developer-Mode 15-ch path)
    if max_ch and max_ch < 12:
        level = _worst(level, BAD)
        reasons.append(f"only {max_ch} accl channels (expected {target_channels})")
    elif max_ch and max_ch < target_channels:
        level = _worst(level, WEAK)
        reasons.append(f"{max_ch} accl channels (expected {target_channels})")

    return Verdict(level=level, reasons=reasons, packets_per_sec=pps,
                   n_accl=n_accl, n_imu=n_imu, fingers=finger_names,
                   n_fingers=len(moved), max_accl_channels=max_ch)
