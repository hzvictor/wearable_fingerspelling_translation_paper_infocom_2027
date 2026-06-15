#!/bin/bash
# Double-clickable launcher for the ASL Fingerspelling Collector.
# Finder runs a .command file in Terminal on double-click — no packaging needed.
#
# First run sets up Pillow (the only third-party dep) for the system Python,
# matching the Mac's native architecture (arm64 on Apple Silicon).

cd "$(dirname "$0")" || exit 1

PY=/usr/bin/python3
ARCH="$(/usr/bin/uname -m)"   # arm64 or x86_64

echo "ASL Collector — starting…"

# Ensure Pillow is importable for the right arch; install to --user if missing.
if ! arch -"$ARCH" "$PY" -c "import PIL.ImageTk" >/dev/null 2>&1; then
  echo "Installing Pillow (one-time)…"
  arch -"$ARCH" "$PY" -m pip install --user --quiet Pillow || {
    echo "Could not install Pillow. Try: arch -$ARCH $PY -m pip install --user Pillow"
    read -r -p "Press Return to close."; exit 1
  }
fi

exec arch -"$ARCH" "$PY" app.py
