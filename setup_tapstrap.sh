#!/usr/bin/env bash
# One-time setup for TapStrap raw data collection on macOS.
# Creates a local venv and installs bleak + the OFFICIAL tap-python-sdk.
set -e

cd "$(dirname "$0")"

echo "[1/4] creating .venv ..."
python3 -m venv .venv

echo "[2/4] upgrading pip ..."
./.venv/bin/pip install -q --upgrade pip

echo "[3/4] installing bleak (BLE) ..."
./.venv/bin/pip install -q "bleak>=0.20"

echo "[4/4] installing official tap-python-sdk ..."
TMP=$(mktemp -d)
git clone --depth 1 https://github.com/TapWithUs/tap-python-sdk "$TMP/tap-python-sdk"
./.venv/bin/pip install -q "$TMP/tap-python-sdk"
rm -rf "$TMP"

echo
echo "Done. Next:"
echo "  1) In the TapManager app, enable Developer Mode."
echo "  2) Pair the Tap in macOS System Settings > Bluetooth."
echo "  3) Run:"
echo "       source .venv/bin/activate"
echo "       python3 tapstrap_mac_test.py"
