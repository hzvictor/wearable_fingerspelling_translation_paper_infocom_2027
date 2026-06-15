"""Headless test for FingerActivityStrip — no display interaction, no hardware.

Run: arch -arm64 /usr/bin/python3 test_signal_strip.py
"""
from collections import deque
import customtkinter as ctk

from ui.signal_strip import FingerActivityStrip


class FakeManager:
    def __init__(self):
        self.recent = deque(maxlen=300)


def frames_for(fingers_moving, n=20):
    """n accl frames where the given finger indices have big motion, others 0."""
    out = []
    for k in range(n):
        pl = []
        for f in range(5):
            if f in fingers_moving:
                pl += [30, -25, 18]   # well above deadband
            else:
                pl += [0, 0, 0]
        out.append({"type": "accl", "ts": k, "payload": pl, "recv_time": k})
    return out


def main():
    ctk.set_appearance_mode("dark")
    root = ctk.CTk(); root.withdraw()
    mgr = FakeManager()
    strip = FingerActivityStrip(root, mgr)
    strip.pack()
    root.update()

    # empty deque must not throw
    strip.refresh()
    assert strip.active_fingers == set(), strip.active_fingers
    print(f"  [ok] empty deque -> no active fingers, no crash")

    # only thumb, index, middle move
    for fr in frames_for({0, 1, 2}):
        mgr.recent.append(fr)
    strip.refresh()
    assert strip.active_fingers == {0, 1, 2}, strip.active_fingers
    print(f"  [ok] fingers 0,1,2 moving -> active={sorted(strip.active_fingers)}")

    # all five move
    mgr.recent.clear()
    for fr in frames_for({0, 1, 2, 3, 4}):
        mgr.recent.append(fr)
    strip.refresh()
    assert strip.active_fingers == {0, 1, 2, 3, 4}, strip.active_fingers
    print(f"  [ok] all fingers moving -> active={sorted(strip.active_fingers)}")

    # below deadband must NOT register
    mgr.recent.clear()
    for k in range(20):
        mgr.recent.append({"type": "accl", "ts": k,
                           "payload": [1, -1, 2] + [0]*12, "recv_time": k})
    strip.refresh()
    assert strip.active_fingers == set(), strip.active_fingers
    print(f"  [ok] sub-deadband motion -> no false positives")

    # drive the animated tick a few cycles under the event loop
    strip.start()
    for _ in range(5):
        root.update()
    strip.stop()
    print(f"  [ok] animated _tick runs without exception")

    root.destroy()
    print("\n✅ ALL signal_strip TESTS PASSED")


if __name__ == "__main__":
    main()
