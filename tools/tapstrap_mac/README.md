# TapStrap macOS Tools

This folder contains one-off TapStrap BLE and official-SDK probe scripts used to understand raw accelerometer streaming behavior on macOS.

## Setup

```bash
cd /Users/houzhen/research/paper_infocom_2027/tools/tapstrap_mac
bash setup_tapstrap.sh
source .venv/bin/activate
```

Before running the scripts, enable Developer Mode in TapManager and make sure the Tap device is advertising or paired as required by the specific probe.

## Scripts

- `tapstrap_mac_test.py`: official SDK baseline probe; checks whether all five fingers arrive without reassembly.
- `tapstrap_mac_official_5finger.py`: current five-finger collector; applies the scan/connect patch and cross-notification reassembly.

Generated CSV captures are written to `../../data/raw/` and are ignored by git.
