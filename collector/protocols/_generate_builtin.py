"""One-time generator: externalize the hardcoded WORD_LIST / GESTURES from the
old Mac scripts into builtin protocol JSON files this app loads at runtime.

Run once (already run during build):
    /usr/bin/python3 protocols/_generate_builtin.py

Reads the dicts from /Users/houzhen/research/finger/tapstrap/{collect_words,collect_gestures}.py
via ast.literal_eval (no import side effects) and writes protocols/builtin/*.json.
"""
import ast
import json
from pathlib import Path

SRC = Path("/Users/houzhen/research/finger/tapstrap")
OUT = Path(__file__).resolve().parent / "builtin"
OUT.mkdir(parents=True, exist_ok=True)


def grab(pyfile: Path, name: str):
    tree = ast.parse(pyfile.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    raise KeyError(name)


def trialdef(prompt, letters, group, hint="", confusion_test=None):
    return {"prompt": prompt, "letters": list(letters), "group": group,
            "hint": hint, "confusion_test": confusion_test, "duration_ms": 0}


def write(protocol):
    p = OUT / f"{protocol['id']}.json"
    p.write_text(json.dumps(protocol, ensure_ascii=False, indent=2))
    print(f"  wrote {p.name}: {len(protocol['trials'])} trials")


def main():
    word_list = grab(SRC / "collect_words.py", "WORD_LIST")
    gestures = grab(SRC / "collect_gestures.py", "GESTURES")

    # --- ASL alphabet (A-Z) ---
    def alpha_group(ch):
        if ch <= "I": return "alpha1"
        if ch <= "R": return "alpha2"
        return "alpha3"
    alpha_trials = [
        trialdef(ch, [ch], alpha_group(ch), hint=gestures[ch][1] if ch in gestures else "")
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ]
    write({"id": "asl_alphabet", "name": "ASL Alphabet (A–Z)", "type": "gesture",
           "builtin": True, "description": "26 single-letter handshapes.",
           "trials": alpha_trials})

    # --- ASL digits (0-9) ---
    digit_trials = [
        trialdef(d, [d], "digits", hint=gestures[d][1] if d in gestures else "")
        for d in "0123456789"
    ]
    write({"id": "asl_digits", "name": "ASL Digits (0–9)", "type": "gesture",
           "builtin": True, "description": "10 single-digit handshapes.",
           "trials": digit_trials})

    # --- word protocols ---
    def word_trials(filter_group=None):
        out = []
        for word, meta in word_list.items():
            if filter_group and meta.get("group") != filter_group:
                continue
            letters = list(meta.get("letters", word))
            out.append(trialdef(word, letters, meta.get("group", ""),
                                 confusion_test=meta.get("test")))
        return out

    write({"id": "confusion_words", "name": "Confusion-pair Words", "type": "word",
           "builtin": True, "description": "Confusable letter sequences (A/S/T/M/N etc.).",
           "trials": word_trials("confusion")})

    write({"id": "all_words", "name": "All Words", "type": "word",
           "builtin": True,
           "description": "Full fingerspelling word set (confusion / coarticulation / "
                          "common / medium / long / phone / url / mixed / phrase).",
           "trials": word_trials()})


if __name__ == "__main__":
    main()
    print("done.")
