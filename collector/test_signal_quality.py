"""Unit tests for core.signal_quality — pure, no Tk, no hardware.

Run: arch -arm64 /usr/bin/python3 test_signal_quality.py
"""
from core.signal_quality import signal_quality, GOOD, WEAK, BAD


def buf(n_accl, n_imu=40, fingers=5, channels=15):
    """Synthetic buffer: n_accl accl frames (each `channels` ints, first
    `fingers` fingers non-zero), plus n_imu imu frames."""
    out = []
    for i in range(n_accl):
        pl = []
        for f in range(channels // 3):
            if f < fingers:
                pl += [((i + f) % 40) - 20 + 1, 2, 3]   # non-zero triplet
            else:
                pl += [0, 0, 0]
        # pad remainder if channels not multiple of 3
        pl += [0] * (channels - len(pl))
        out.append({"type": "accl", "ts": i, "payload": pl, "recv_time": i * 0.005})
    for i in range(n_imu):
        out.append({"type": "imu", "ts": i, "payload": [0, 0, 0, 1, 2, 3], "recv_time": i})
    return out


def check(name, verdict, expect_level, expect_fingers=None):
    ok = verdict.level == expect_level
    if expect_fingers is not None:
        ok = ok and verdict.n_fingers == expect_fingers
    status = "ok" if ok else "FAIL"
    print(f"  [{status}] {name}: level={verdict.level} fingers={verdict.n_fingers} "
          f"pps={verdict.packets_per_sec:.0f} ch={verdict.max_accl_channels} "
          f"| {verdict.reasons}")
    assert ok, f"{name}: got {verdict.level}/{verdict.n_fingers}, want {expect_level}/{expect_fingers}"


def main():
    # GOOD: 4s @190Hz = 760 frames, 5 fingers, 15ch
    check("GOOD full", signal_quality(buf(760, fingers=5, channels=15), 4.0), GOOD, 5)

    # WEAK rate: ~0.5x -> 380 frames over 4s
    check("WEAK low-rate", signal_quality(buf(380, fingers=5), 4.0), WEAK)

    # WEAK fingers: full rate, only 4 fingers
    check("WEAK 4-finger", signal_quality(buf(760, fingers=4), 4.0), WEAK, 4)

    # WEAK channels: 13 channels (between 12 and 15)
    check("WEAK 13ch", signal_quality(buf(760, fingers=5, channels=13), 4.0), WEAK)

    # BAD: few frames (absolute floor)
    check("BAD few-frames", signal_quality(buf(20, fingers=5), 4.0), BAD)

    # BAD: 2 fingers
    check("BAD 2-finger", signal_quality(buf(760, fingers=2), 4.0), BAD, 2)

    # BAD: low rate (<0.4x) -> 200 frames over 4s = 50/s < 76
    check("BAD very-low-rate", signal_quality(buf(200, fingers=5), 4.0), BAD)

    # BAD: low channels (9ch = IMU-ish/8ch fallback path)
    check("BAD 9ch", signal_quality(buf(760, fingers=3, channels=9), 4.0), BAD)

    # boundary: exactly 0.70x rate => GOOD edge (0.70*190*4 = 532 frames)
    check("boundary GOOD@0.70", signal_quality(buf(532, fingers=5), 4.0), GOOD)
    # just below 0.70 => WEAK (530 frames)
    check("boundary WEAK<0.70", signal_quality(buf(530, fingers=5), 4.0), WEAK)
    # exactly 0.40x => WEAK edge (0.40*190*4 = 304)
    check("boundary WEAK@0.40", signal_quality(buf(304, fingers=5), 4.0), WEAK)
    # just below 0.40 => BAD (302)
    check("boundary BAD<0.40", signal_quality(buf(302, fingers=5), 4.0), BAD)

    # summary/banner copy sanity
    v = signal_quality(buf(760, fingers=5), 4.0)
    s = v.summary("CAT")
    assert "CAT" in s and "frames" in s and "fingers" in s, s
    print(f"  summary GOOD: {s!r}")
    vb = signal_quality(buf(15, fingers=2), 4.0)
    print(f"  summary BAD : {vb.summary('DOG')!r}")
    print(f"  banner BAD  : {vb.decide_banner()!r}")

    print("\n✅ ALL signal_quality TESTS PASSED")


if __name__ == "__main__":
    main()
