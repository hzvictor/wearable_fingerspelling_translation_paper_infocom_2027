# ASL Fingerspelling Collector (macOS)

A user-centric desktop app to collect Tap Strap 2 fingerspelling data: pick a
**Subject** + **Protocol**, run a guided **PREP → SPELLING → DECIDE** session,
save **local JSON** (source of truth), and **auto-sync to Firebase** (no login).
Full **15-channel** (5 fingers × XYZ) stream @ ~190 Hz.

## Run from source

```bash
cd /Users/houzhen/research/paper_infocom_2027/collector
/usr/bin/python3 app.py
```

Prerequisites:
- **TapManager → Developer Mode ON** (unlocks the 15-channel stream).
- Tap Strap connected to this Mac as a keyboard (System Settings ▸ Bluetooth).
- macOS system Python 3.9 (`/usr/bin/python3`) — has tkinter + pyobjc. Plus
  `Pillow` (arm64): `arch -arm64 /usr/bin/python3 -m pip install --user Pillow`.

## Architecture

```
app.py                 entry: Tk root + CBCentralManager + RunLoopPump + Router
ble/                   CoreBluetooth: constants, parser (parse_raw), manager, runloop pump
core/                  models, ids, paths, local JSON store, audio, collection_controller
protocols/             builtin/*.json (alphabet/digits/confusion/all_words) + loader
sync/                  firebase (urllib, no-login Firestore) + syncer (bg thread)
ui/                    router, theme, widgets + screens: home/device/subjects/
                       session_setup/collection(+canvas)/sessions
```

Key design points:
- **CoreBluetooth runs on the main thread**, pumped from Tk via `RunLoopPump`
  (`root.after` ticks `NSRunLoop.runUntilDate_`). No background BLE thread.
- **Collection canvas is native Tk + Pillow** (no matplotlib). If optional
  reference handshape images are absent, the UI falls back to letter prompts.
- **Local-first**: every accepted trial is written atomically to
  `~/Library/Application Support/ASLCollector/sessions/{id}/trial_NNN.json`
  in the unified word-shaped schema (compatible with
  `finger/tapstrap/prepare_finetune_data.py`). Firebase is a best-effort mirror.

## Data locations

- Sessions/trials: `~/Library/Application Support/ASLCollector/sessions/{session_id}/`
- Subjects: `~/Library/Application Support/ASLCollector/subjects.json`
- Firebase config: `~/Library/Application Support/ASLCollector/firebase_config.json`
  (`{"projectId","apiKey","collector"}`; sync is skipped if absent)
- Sync manifest: `~/Library/Application Support/ASLCollector/.synced.json`

## Firebase (no login)

Firestore collections: `subjects`, `sessions`, `trials` (each trial doc carries
gzip+base64 `raw_gz`). Open ("test mode → `if true`") rules; the public Web
apiKey is embedded. Free Spark tier is sufficient (~70 KB/trial compressed).

Packaging files were removed from this paper repository. Recreate them in a
separate app-release repository if the collector needs to be distributed.
