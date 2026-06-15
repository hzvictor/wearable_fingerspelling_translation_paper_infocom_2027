# Active Collection — Enhanced Spec (with Test Guideline)

> Based on Mac `collect_words.py` + `collect_gestures.py` protocol. The screen MUST give the subject clear "when to do what gesture" guidance.

## Source of truth (Mac protocol)

### Phases (from `collect_words.py:443-507`)

```
1. PREP (3s)          : "GET READY" banner (blue #0f3460), word displayed centered,
                        all letters in muted teal, ASL reference image (GIF) shown
                        UNDER each letter side-by-side.
                        Voice: "Please spell {word}"
                        Beeps: 3-2-1 countdown (1 beep/s)

2. SPELLING (N s)     : "SPELLING (Ns)" banner (red #e94560).
                        Word stays. Current letter:
                            - color #e94560 (red), bold, size 28
                            - others: gray #666666, normal, size 22
                        time_per_letter = collect_time / len(word)
                        Letter highlight moves through word at this cadence.
                        Voice: "Go" + beep_start at phase entry
                        beep_done + voice "Good" at phase exit

3. DECIDE             : ENTER = keep, R = redo (voice "Redo"), D = discard (voice "Discarded")
                        On Android: 3 buttons (Accept / Redo / Skip).
```

### Per-letter timing (from `collect_words.py:467-477`)

```python
time_per_letter = collect_time / len(word)
for li in range(len(word)):
    display.show_word(word, ..., phase="collect",
                      collect_time=collect_time, highlight_idx=li)
    time.sleep(time_per_letter)
```

So if `CAT` is 4s total, each letter highlights for ~1.33s.

### Collect time formula (`collect_words.py:235`)

```python
def get_collect_time(word):
    return max(3.0, 1.0 * len(word) + 1.0)
# CAT  (3 chars) -> 4s
# HELLO (5)      -> 6s
# 911 (3)        -> 4s
```

### Voice cues (Mac uses macOS `say`)

| Phase | Voice line |
|---|---|
| PREP entry | "Please spell {word}" |
| SPELLING entry | "Go" |
| SPELLING exit | "Good" |
| Redo | "Redo" |
| Discard | "Discarded" |
| Group complete | "Group complete. Next group: {curr_group}. Press enter when ready." |

### Reference assets

`/Users/houzhen/research/finger/tapstrap/asl_reference/`:
- `A.gif` ... `Z.gif` — 26 ASL letter handshape animations
- `0.jpg` ... `9.jpg` — 10 ASL digit handshapes

These are real GIFs/JPGs. Paper can load them via `paper-asset:///Users/houzhen/research/finger/tapstrap/asl_reference/A.gif`.

### Letter description (`collect_words.py` uses LETTER_DESC dict)

Each letter has a short tooltip like "Fist with thumb on side" (A) — same descriptions live in `collect_gestures.py:GESTURES` dict and in the seeded `asl_alphabet.json`.

## Android Active Collection layout (Paper redesign target)

```
┌─────────────────────────────────────┐
│ ←  S001 · Confusion Words   ⏸  3/20 │  ← Top bar: subject/protocol + Pause icon + count
│ ▓▓▓░░░░░░░░░░░░░░░ 15%             │
├─────────────────────────────────────┤
│ ┌─────────────────────────────────┐ │
│ │ ●  SPELLING · 2.3s left   [4s]  │ │  ← Status banner (red when SPELLING, blue when PREP)
│ └─────────────────────────────────┘ │
│                                     │
│            S P E L L                │  ← Small label
│                                     │
│            CAT                      │  ← Big word, 70px, monospace bold
│                                     │
│         C    A    T                 │  ← Letter sequence (current bigger+red, others gray)
│         •         •                 │  ← Dot indicators below muted letters
│                                     │
│   ┌──────┐  ┌──────┐  ┌──────┐     │  ← Reference GIFs strip (one per letter)
│   │ [C]  │  │ [A]  │  │ [T]  │     │  Current letter's frame: red border, bigger
│   │ gif  │  │ gif  │  │ gif  │     │  Others: smaller, muted
│   │ Curve│  │ Fist │  │ Thumb│     │  Tiny hint text under each
│   │  hand│  │ +thb │  │  bw  │     │
│   └──────┘  └──────┘  └──────┘     │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 📹  Camera preview (subtle)     │ │  ← 16:9 frame, small
│ └─────────────────────────────────┘ │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ LIVE IMU         ●thumb ●idx ●mid│ │  ← Mini chart with labels TOP-RIGHT (not over waves)
│ │ ╱╲╱╲╱╲╱╲╱╲╱╲╱╲                  │ │
│ └─────────────────────────────────┘ │
│                                     │
│   ⏮       ↻       ✗                │  ← Small secondary controls
│  Prev    Redo    Skip               │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │      ▶  NEXT TRIAL              │ │  ← Big primary action — only thing you usually press
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Sub-states to render in 4 distinct artboards

To show the timing protocol clearly, draw 4 mini-states (one per artboard OR as horizontal strip inside one):

**8a · PREP**
- Banner blue "● GET READY · 3s"
- All 3 letters teal, all 3 GIF frames same size, no current-letter highlight
- Tooltip text: "Voice: Please spell CAT"

**8b · SPELLING letter 1 (C)**
- Banner red "● SPELLING · 4s ▶ 2.7s left"
- Letter "C" big red bold, A and T gray
- C's GIF frame: red border + 1.2× scale; A and T: muted, smaller
- "Voice: Go" small footer

**8c · SPELLING letter 2 (A)**
- Same banner pattern
- A highlighted, C/T muted
- A's GIF in focus

**8d · DECIDE**
- Banner green "✓ DONE · 0.0s"
- All letters teal, all GIFs equal
- Bottom: 3 buttons (Accept / Redo / Skip)
- "Voice: Good. Press Accept to continue"

If only one artboard, show state 8b (SPELLING mid-trial) since that's the visually richest moment.

## Why this matters

Without letter-by-letter guidance + reference GIF, the subject (especially a non-fluent signer) has NO IDEA:
- which letter to make right now
- what the hand shape looks like
- when to start / stop / move on

This is the core delta between "looks like a UI demo" and "researcher can run actual sessions."
