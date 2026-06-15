# Tap Strap Android Collector — Product Specification v0.3

> Refinement of the approved plan (`zippy-weaving-hummingbird.md`) and wireframes (`/Users/houzhen/research/paper_infocom_2027/docs/wireframes.md`). This document does NOT re-litigate stack/architecture decisions already accepted; it surfaces gaps, edge cases, copy, and ordering needed to ship MVP. Audience: implementer + PI. Date: 2026-05-25.

---

## 0. Executive summary

The accepted plan defines a 13-screen Compose app, 5 Room entities, and a Mac-byte-compatible JSON output format. The spike skeleton (`/Users/houzhen/research/paper_infocom_2027/spike_android/`) has Home + Device Setup working end-to-end with the real BLE+MTU pipeline; the other 11 screens are `PlaceholderScreen` stubs.

This spec resolves:
- **34 concrete UI/UX gaps** the wireframes glossed over (empty/loading/error states, exact copy, validation rules).
- **17 edge cases** the original plan did not address (BLE drop mid-trial, camera-denied fallback, storage full, rotation, background, etc.).
- **JSON format ambiguities** between gesture and word collectors (the Mac code emits two different shapes — Android must choose one).
- **13 deliverable subsystems** with concrete file-by-file build order.
- **12 open questions** that need a human decision before Phase 1 freeze (10 inherited, 2 new).

**Three most consequential open questions still unresolved:**
1. Trial JSON schema unification (`gesture_id`/`word` discrepancy — Mac emits both shapes; Android must commit to one for the training pipeline).
2. Whether "Active Collection" runs as a foreground Service (correct answer: yes, but it adds 2-3 days work and a permission); the plan punts on this.
3. Recovery semantics on crash: auto-resume vs. discard partial session — this dictates whether the session row needs an `incomplete` enum state and whether trials are written atomically per-trial vs. at session-end.

**Spike alignment**: The current skeleton is **structurally correct**. Package layout, entities, DAOs, Hilt setup, navigation graph, and the BLE Flow are all in line with this spec. The only restructuring needed is **renaming the module from `tapstrapspike` to a final name** (`spike_android/` directory rename optional) and **converting MTU detection from "live observation" to a stored Session field**.

---

## 1. Cross-cutting decisions (apply before per-screen detail)

### 1.1 Trial JSON schema — UNIFIED (resolves Mac inconsistency)

The Mac code emits two schemas:
- **Gestures** (`collect_gestures.py:797`): top-level `{session_id, config, gesture_definitions, summary, trials:[ {gesture_id, gesture_name, trial, ...} ]}`. All trials in one file.
- **Words** (`collect_words.py:516`): top-level `{session_id, config, word_definitions, summary, trials:[ {word, letters, num_letters, group, confusion_test, trial, ...} ]}`. All trials in one file.

The accepted plan and `prepare_finetune_data.py` expect the **word** schema (looks for `trial.get('word')`, `trial.get('letters')`). It is also the schema the paper cares about (fingerspelling, not isolated gestures).

**Decision**: Android emits **one schema for both gesture and word protocols**, modeled on the word format. For `type == "gesture"` protocols, set:
- `word` = the single letter (e.g. `"A"`)
- `letters` = `["A"]`
- `num_letters` = `1`
- `group` = the trial-def `group` (e.g. `"alpha1"`, `"digits"`)
- `confusion_test` = the trial-def `confusionTest` (nullable)

This makes `prepare_finetune_data.py` treat gestures as 1-letter words — which is already what the pipeline assumes via `''.join(letters).lower()`.

**File-per-trial vs. file-per-session**: The Mac code writes **one file per session**. The plan says **one file per trial** (`trial_001.json`). Argue for file-per-trial:
- Atomic durability after each trial (crash recovery trivial).
- Smaller `JSONObject` to serialize on phone (avoids re-encoding the entire session on every save).
- Easier to delete/reject a single bad trial.

Cost: `prepare_finetune_data.py` currently does `for trial in data['trials']`. We must either (a) ship an `aggregate.py` step on the Mac side that merges per-trial files into a session JSON before training, or (b) extend `prepare_finetune_data.py` to also walk `trial_*.json` directly. (b) is one-line: `for fpath in glob('.../trial_*.json'): trial = json.load(f); finger, imu = parse_trial(trial)`.

**Decision**: file-per-trial on Android, plus a `meta.json` per session with the merged config (Mac-readable). Update `prepare_finetune_data.py` to handle either layout (5 lines of code).

### 1.2 Per-packet `recv_time` is **wall-clock seconds (float)**, not ms

The Mac side uses `time.time()` → float seconds since epoch. `prepare_finetune_data.py` calls `np.interp(t_target, accl_times, …)` on these and assumes a uniform unit. **Android must emit `recv_time` as `System.currentTimeMillis() / 1000.0`** (double, 3 decimals). The spike currently stores Long ms in `BlePacket.recvTimeMs` — fine, but conversion happens at JSON write time.

### 1.3 `payload` field semantics

Mac `parse_raw` truncates the list to `n_actual` (8 for accl on Mac, 15 for accl on Android if MTU succeeds, 6 for imu always). `prepare_finetune_data.py:33` filters `len(p['payload']) >= 8` and only ever consumes `p[1][:8]`. So Android can safely emit the full 15-channel list when available, and old Mac data with 8 channels remains compatible.

**Decision**: Emit `payload` with exactly `nActual` ints (no zero-padding). This matches Mac and avoids breaking the existing 1006 samples.

### 1.4 Time base for `ts` (Tap Strap device clock)

`ts` is the Tap Strap onboard 32-bit timer (`RAW_MSG_TYPE_BIT` strips the high bit for accl). The pipeline does NOT use it (only `recv_time`). Emit it verbatim from `RawParser.Message.timestamp` — it's diagnostic only.

### 1.5 Session ID format

Mac uses `datetime.now().strftime("%Y%m%d_%H%M%S")` (e.g. `20260524_142312`). Reuse exactly. UUIDs are uglier and harder to grep. Add `_<random4>` only on collision (extremely unlikely; two sessions in the same second).

### 1.6 Foreground Service for Active Collection

The plan does not explicitly require it. **MUST be a foreground Service** because:
- Screen-off mid-trial would kill the BLE callback in a regular Activity (Android 12+ background BLE restrictions).
- CameraX `VideoCapture` requires the host lifecycle alive.
- If the user accidentally swipes home, the trial in progress must not lose data.

Spec: `CollectionService : LifecycleService`, started with `startForeground()` displaying a persistent notification "Recording trial X of Y · S001 · Tap to return". Activity binds to it; ViewModel reads state from the service via a `StateFlow`. Permission `FOREGROUND_SERVICE_CAMERA` (Android 14+) and `FOREGROUND_SERVICE_CONNECTED_DEVICE` (BLE) needed in manifest.

### 1.7 Rotation policy

Active Collection is **locked to portrait** (`activity android:screenOrientation="portrait"` for `CollectActivity` if separate, otherwise `requestedOrientation` in the Activity onCreate when entering Collect). Other screens follow system. Rationale: the prompt card, camera preview, and waveform layout depend on portrait; landscape rotation mid-trial would re-create the CameraX surface and corrupt the MP4.

### 1.8 Audio routing during recording

Beep + TTS would leak into the MP4 audio track. Options:
- (A) Mute audio capture in CameraX (`VideoCapture.Builder().setAudioConfig(AudioConfig.AUDIO_DISABLED)`) — simplest, but loses the synced spoken prompt as a label.
- (B) Record audio, accept beeps.
- (C) Record audio, but route TTS to a different audio session that doesn't go to the mic (impossible — mic captures speaker).

**Decision**: (A) — no audio in MP4 by default. The TTS prompt is logged textually in `trial_NNN.json` (`word` field) and doesn't need to be in the video. Add a Setting "Record audio (debug)" defaulting OFF.

### 1.9 Per-trial recording duration

The Mac word collector uses `max(3.0, len(word)*1.0 + 1.0)` seconds (`get_collect_time`). Mac gesture collector uses fixed `args.collect_time` (default 1.5s). The Android `TrialDefEntity.estimatedDurationMs` is the source of truth — populated when seeding builtin protocols and editable in Protocol Editor. Default for word: `max(3000, 1000 * letters + 1000)`. Default for gesture: `2000`.

### 1.10 Permission gating

Required permission groups (declared in manifest, requested at runtime):
- BLE (`BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT`): requested on Device Setup screen entry.
- Camera (`CAMERA`): requested on Session Setup screen if "Record video" is checked, OR on first entry to Active Collection.
- Foreground service variants on Android 14+.
- No `RECORD_AUDIO` needed (we disable audio per §1.8). Remove from manifest.
- No storage permissions for Android 10+ (using app-specific external storage).
- `POST_NOTIFICATIONS` on Android 13+ for the foreground service notification.

### 1.11 Empty/loading/error state conventions

Standardize three components in `ui/components/`:
- `EmptyState(icon, title, body, ctaLabel?, onCta)` — used wherever a Lazy list is empty.
- `LoadingState()` — center-aligned `CircularProgressIndicator`.
- `ErrorBanner(message, onRetry?)` — top-of-screen error surface.

All copy below uses these.

---

## 2. Per-screen specification (deep)

For each screen: **Purpose · States · Widgets · Actions · Nav out · Reads · Writes · Validation · Copy**.

---

### Screen 1 — Home / Dashboard

**Purpose**: Single glance at app state; one-tap entry to start a new session.

**States**:
- Initial / loading: shows zero counts (acceptable; ViewModel `WhileSubscribed(5000)` already used). No spinner needed — counts populate in <200ms.
- Connected / Disconnected device card variants.
- BLE off: device card shows "Bluetooth is off" with a tappable hint that opens system BT settings via `Intent(Settings.ACTION_BLUETOOTH_SETTINGS)`.

**Widgets** (Compose):
- `TopAppBar("TapStrap Collector")` (no nav icon — root).
- `DeviceCard` (already implemented in spike).
- `CountCard × 3` (Subjects, Protocols, Sessions — already implemented).
- Primary `Button("Start New Session")` — **disabled** when `subjectCount == 0 || protocolCount == 0 || device != Connected`. Tooltip / supporting text: "Need at least 1 subject and a connected device."
- `TextButton("Settings")`.

**Actions**:
- Tap any card → navigate to corresponding screen (already wired).
- Tap Start → `nav.navigate(Routes.SESSION_SETUP)`.
- Tap Settings → settings.
- Back from Home → minimize app (default Compose nav behavior).

**Nav out**: Device(2), Subjects(3), Protocols(5), Sessions(10), SessionSetup(7), Settings(13).

**Reads**: `TapStrapClient.conn`, `SubjectDao.count()`, `ProtocolDao.count()`, `SessionDao.count()`.

**Writes**: none.

**Validation**: see "Start" enable rule above.

**Copy delta vs wireframe**:
- Wireframe shows "Last: S007 · 2 hours ago" as device subline — drop until Phase 5 (requires querying last session — not in HomeState yet).
- Add disabled-state hint text under Start CTA: "Connect Tap Strap and create a subject to begin."

**Implementation status**: ✅ Done in spike. Only the disabled-state logic is missing.

---

### Screen 2 — Device Setup

**Purpose**: Establish BLE connection, validate that MTU and channel count meet the paper's requirements, give the researcher confidence the device "feels right".

**States**:
- `Idle`, `Scanning`, `Connecting(mac)`, `Connected(mac, mtu)`, `Failed(reason)`.
- Permission-not-granted (before any scan attempt).
- Bluetooth-off (adapter null or disabled).

**Widgets**:
- `TopAppBar("Device", back)`.
- `ConnectionBanner` (implemented).
- Row of `Button("Scan & Connect")` + `OutlinedButton("Disconnect")`.
- `MetricsCard` (implemented) — MTU, Max packet size, Max accl channels (the ⭐ number), packet count.
- **NEW**: `WaveformCard` — Vico line chart, last 3 seconds, one trace per available accl channel (or aggregate norm). Updates at 10 Hz max (downsample).
- **NEW**: `Card("Test trial")` — `OutlinedButton("Record 2s test")` that runs a discarded recording to confirm pipeline. On completion, shows `"Got 95 pkts (50 accl, 45 imu) — looks good ✓"`. No write to disk.
- Help card (implemented) — already explains MTU.

**Actions**:
- Tap Scan → check permissions → if missing, launch permission flow → on grant, `vm.scan()`.
- Tap Disconnect → `vm.disconnect()`.
- Tap "Record 2s test" → in-memory BLE collection for 2000 ms, no file write.
- Back → pop. Connection persists (BLE client is `@Singleton`).

**Nav out**: back to Home.

**Reads**: `TapStrapClient.conn`, `TapStrapClient.packets()` (live preview).

**Writes**: none persisted. (`SessionEntity.maxAcclChannelsSeen` is written later by Active Collection, **not** here.)

**Validation**:
- If BLE adapter null → show error banner with "Bluetooth not supported on this device" and disable Scan button permanently.
- If adapter off → banner "Bluetooth is off" + button "Open Bluetooth settings".
- Spike's `Connection.Failed` reasons need user-readable mapping (currently shows raw error codes).

**Empty/Error copy**:
- Idle: "Tap Strap not connected. Tap **Scan & Connect** to start."
- Scanning: "Scanning for Tap Strap (up to 30 s)..." (NEW: add 30 s timeout to spike, currently scan never stops).
- Failed("Scan failed: 2"): map error code 2 → "Bluetooth scan already running. Wait 30 s and try again."

**Implementation status**: ✅ ~80% done. Missing: live waveform, test-trial button, scan timeout, permission re-prompt loop, BT-off recovery.

---

### Screen 3 — Subjects List

**Purpose**: Browse and manage subject library.

**States**:
- Empty (no subjects yet) — distinct from loading.
- Populated.
- Searching (filtering live).

**Widgets**:
- `TopAppBar("Subjects", back, action: search icon → expands search field)`.
- `OutlinedTextField` (search, when expanded).
- `LazyColumn` of `SubjectRow(subject, sessionCount)` cards.
- `FloatingActionButton("+ New")` — extended FAB with icon + label.

**SubjectRow** shows:
- Left: subject ID monospace + display name.
- Right top: dominant hand chip (L/R).
- Right bottom: `"$sessionCount sessions · last 2d ago"` or `"No sessions yet"`.
- Trailing chevron `>`.

**Actions**:
- Tap row → `Routes.subjectEdit(s.id)`.
- Long-press → `AlertDialog("Delete subject S001? This cannot be undone. Sessions for this subject will be kept.")` with Cancel/Delete.
- Tap FAB → `Routes.SUBJECT_NEW`.
- Search text changes → filter via `derivedStateOf`.

**Nav out**: SubjectEditor(4) for new or edit.

**Reads**: `SubjectDao.observeAll()`. **NEW DAO needed**: `@Query("SELECT s.*, (SELECT COUNT(*) FROM sessions WHERE subjectId = s.id) AS sessionCount, (SELECT MAX(startedAt) FROM sessions WHERE subjectId = s.id) AS lastSessionAt FROM subjects s ORDER BY s.updatedAt DESC")` returning a `SubjectWithStats` projection.

**Writes**: `SubjectDao.delete()` on confirm.

**Validation on delete**: FK is `RESTRICT` from `sessions` — deletion will throw if subject has sessions. Handle: catch SQLiteConstraintException → show snackbar "Cannot delete: subject has N sessions. Delete the sessions first."

**Empty copy**:
- Empty: `EmptyState(icon=Person, title="No subjects yet", body="Add your first participant before starting a session.", cta="+ Add subject")`.

**Implementation status**: ❌ Placeholder only.

---

### Screen 4 — Subject Editor

**Purpose**: Create / edit subject details + capture consent + show that subject's sessions.

**States**:
- New mode (`id == null`): all fields blank, save button reads "Create".
- Edit mode: pre-filled, save button reads "Save".
- Dirty: any change vs original → unsaved-changes prompt on Back.

**Widgets** (vertically scrollable):
- `TopAppBar(title, back-with-dirty-check, action: TextButton("Save"))`.
- `OutlinedTextField("ID")` — in new mode pre-filled with next `Snnn` (auto-incremented; query `MAX(id)` where id matches `S\d{3}` regex). Editable. In edit mode: read-only.
- `OutlinedTextField("Display Name *")` (required, max 80 chars).
- Row of `RadioButton` for "Dominant Hand *": Left | Right.
- `OutlinedTextField("Hand Length (cm)")` numeric (0.0–30.0 range allowed; optional).
- `ExposedDropdownMenuBox("Age Range")`: items `["<18","18-29","30-39","40-49","50-59","60+","Prefer not to say"]`.
- `ExposedDropdownMenuBox("Gender")`: `["Male","Female","Non-binary","Prefer not to say","Other"]`.
- Multi-line `OutlinedTextField("Notes", maxLines=4)`.
- **Consent block**:
  - Expandable `Card` — collapsed shows "Consent form (tap to read)"; expanded shows IRB consent full text (loaded from `assets/consent_en.txt` for v1; if no IRB text yet, ship Lorem Ipsum placeholder with red "PLACEHOLDER — replace before IRB submission" banner).
  - `Checkbox("Subject has read and accepted the consent")` — disabled in edit mode if already consented (consent is once-only, immutable timestamp).
  - On check: capture `consentAt = System.currentTimeMillis()` and show `"Consented at 2026-05-25 14:23:12"` once saved.
- **Sessions sub-section** (edit mode only): `LazyColumn` (nested, max-height 200dp) of past sessions for this subject (date · protocol name · trial count). Tap → SessionDetail(11).

**Actions**:
- Save → validate → `SubjectDao.upsert()` → `nav.popBackStack()`.
- Back with dirty → `AlertDialog("Discard changes?")` Cancel/Discard.
- Tap session row → `Routes.sessionDetail(id)`.

**Nav out**: back to Subjects list; into Session Detail(11).

**Reads**: `SubjectDao.byId()`, `SessionDao.observeBySubject()`.

**Writes**: `SubjectDao.upsert()` — set `createdAt = old?.createdAt ?: now`, `updatedAt = now`, `consentAt = old?.consentAt ?: (if checked, now else null)`.

**Validation rules**:
- `id`: required, must match `^[A-Za-z0-9_-]{1,16}$`, unique (check via `byId`).
- `displayName`: required, length 1-80.
- `dominantHand`: required, "L" or "R".
- `handLengthCm`: if present, 5.0 ≤ x ≤ 30.0.
- Save button disabled until required fields valid.

**Copy**:
- Validation errors: red helper text under offending field, e.g. "Required", "Already in use", "Must be between 5 and 30 cm".

**Implementation status**: ❌ Placeholder only.

---

### Screen 5 — Protocols List

**Purpose**: Browse built-in and custom protocols.

**States**: empty (impossible after first launch — builtins are seeded; but show "Loading built-in protocols..." for the first <1s on first launch).

**Widgets**:
- `TopAppBar("Protocols", back)`.
- Two sections via sticky headers in LazyColumn:
  - `"Built-in"` — `🔒` icon prefix on each row.
  - `"Custom"` — editable.
- Each row: name, "$trialCount trials · $type", chevron.
- Extended FAB `"+ New protocol"` (custom only).

**Actions**:
- Tap row → `Routes.protocolEdit(id)` (Editor in read-only or edit mode).
- Long-press custom row → confirm delete (`AlertDialog("Delete '$name'? This won't affect past sessions.")`).
- Long-press built-in → snackbar "Built-in protocols cannot be deleted." (don't show dialog).
- Tap FAB → `Routes.PROTOCOL_NEW`.

**Nav out**: ProtocolEditor(6).

**Reads**: `ProtocolDao.observeAll()` + a count-of-trials projection (`@Query SELECT p.*, (SELECT COUNT(*) FROM trial_defs WHERE protocolId = p.id) AS trialCount FROM protocols p ORDER BY builtin DESC, name ASC`).

**Writes**: `ProtocolDao.delete()` (cascades trial_defs).

**Seeding (one-time, on first DB creation)**: in `AppDatabase.Callback.onCreate`, run a coroutine that reads `assets/builtin_protocols/*.json` and writes 4 protocols + their trials:
1. `asl_alphabet` (26 trials, type=gesture, group=alpha1/alpha2/alpha3).
2. `asl_digits` (10 trials, type=gesture, group=digits).
3. `confusion_words` (20 trials from `WORD_LIST` group=confusion, type=word).
4. `all_words` (143 trials = all of `WORD_LIST`, type=word).

The seed JSON files are generated **once on the Mac** via a 30-line Python script (`scripts/export_builtin_protocols.py`) that reads `collect_words.WORD_LIST` and `collect_gestures.GESTURES` and emits the asset JSONs. This guarantees they stay in sync if the Mac word list ever changes.

**Implementation status**: ❌ Placeholder only; seeding code not written; assets not exported.

---

### Screen 6 — Protocol Editor

**Purpose**: View/edit a protocol + CRUD its trials.

**States**:
- Built-in read-only: all inputs disabled, FAB hidden, delete buttons hidden, "Built-in protocol" banner at top.
- Custom new: blank.
- Custom edit: prefilled.
- Dirty + back: confirm.

**Widgets**:
- `TopAppBar(title, back, action: Save unless read-only)`.
- If built-in: red `Surface` banner "Read-only built-in protocol".
- `OutlinedTextField("Name *")`.
- `RadioGroup("Type *", ["word", "gesture"])`.
- `OutlinedTextField("Description", maxLines=2)`.
- Section header "Trials (N)" + reorder hint icon.
- **Reorderable LazyColumn** of trial rows. Each row:
  - Drag handle (`≡`).
  - Order number + prompt (e.g. "1. CAT").
  - Expected letters as small subtitle.
  - Trailing delete `✗` (custom only).
  - Tap → opens `ModalBottomSheet` for editing one trial (fields: `prompt*`, `expectedLetters*`, `hint`, `group` dropdown, `confusionTest`, `estimatedDurationMs` slider 1000-15000).
- "+ Add trial" outlined button at bottom (custom only).

**Actions**:
- Drag-reorder → updates an in-memory list, only persisted on Save.
- Tap row → bottom sheet edit.
- Delete row → in-memory remove + snackbar with Undo.
- Add → bottom sheet new.
- Save → `ProtocolDao.replaceProtocolWithTrials()` (transactional, already implemented).

**Reorderable implementation**: use `org.burnoutcrew.composereorderable:reorderable:0.9.6` (small lib) OR roll a simple swap-by-tap-up/down — pragmatically the latter for MVP since editing custom protocols is rare in the field.

**Nav out**: back to Protocols list.

**Reads**: `ProtocolDao.byId()`, `ProtocolDao.trialsForProtocol()`.

**Writes**: `ProtocolDao.replaceProtocolWithTrials()`.

**Validation**:
- Name required, unique (case-insensitive vs other protocols).
- Each trial: prompt required, expectedLetters required (auto-fill from prompt if blank).
- If type=word: prompt and expectedLetters must contain only A-Z + 0-9 + hyphen (after upper-casing).
- estimatedDurationMs: 500 ≤ x ≤ 30000.

**Implementation status**: ❌ Placeholder only.

---

### Screen 7 — Session Setup

**Purpose**: Bind a Subject + Protocol + options → create a Session row → enter Collect.

**States**:
- No subjects: show inline EmptyState with "+ Add subject" CTA (instead of empty dropdown).
- No protocols: same.
- Device disconnected: red banner "Tap Strap not connected" + button "Connect now" → DeviceSetup.
- Ready: Start enabled.

**Widgets**:
- `TopAppBar("New Session", back)`.
- `ExposedDropdownMenuBox("Subject *")` — items show "S001 · Alice Chen (R)". Pre-select last-used subject (DataStore key `lastSubjectId`).
- `ExposedDropdownMenuBox("Protocol *")` — items show name + trial count. Pre-select last-used.
- "Subset" `Card`:
  - `Checkbox("All groups")`.
  - Or: per-group checkboxes with counts, derived from selected protocol's trial_defs grouped by `group`.
- Options `Column`:
  - `Switch("Record video (back camera)")` — default ON.
  - `Switch("TTS read prompt aloud")` — default ON.
  - `Switch("Beep on countdown")` — default ON.
- Computed summary `Text`: "Will run N trials, est. M min" (sum of `estimatedDurationMs` + per-trial overhead of 4s for prep/confirm).
- Device status line: "Device: ✓ Connected · last seen 15 channels" or "✗ Disconnected".
- Primary `Button("▶ Start Session")` — disabled unless subject + protocol selected and device connected.

**Actions**:
- Selections live-update summary.
- Start → create `SessionEntity { id, subjectId, protocolId, deviceMac, negotiatedMtu, maxAcclChannelsSeen = 0, targetTrialsCount = filteredTrials.size, startedAt = now, endedAt = null, completed = false }` → persist DataStore preferences (lastSubjectId, lastProtocolId, etc.) → `nav.navigate(Routes.collectScreen(sessionId, filteredTrialIds))` with `popUpTo(SESSION_SETUP) { inclusive = true }` so Back from Collect goes Home not back to Setup.

**Nav out**: ActiveCollection(8).

**Reads**: `SubjectDao.observeAll()`, `ProtocolDao.observeAll()`, `ProtocolDao.observeTrialsForProtocol(selectedProtocolId)`, `TapStrapClient.conn`, DataStore prefs.

**Writes**: `SessionDao.upsert()` (the new session row), DataStore prefs.

**Validation**:
- Subject required, Protocol required.
- At least 1 trial in subset.
- Camera permission required if "Record video" ON — request inline before Start (rationale dialog if previously denied).

**Empty/error copy**:
- "No subjects" inline card with `+ Add subject` button → Subject Editor (4) `id=null`.

**Implementation status**: ❌ Placeholder only.

---

### Screen 8 — Active Collection (★ CORE)

**Purpose**: Drive the trial loop. Capture IMU + video atomically per trial. This is the highest-stakes screen.

**State machine** (in `CollectionViewModel` backed by `CollectionService`):

```
IDLE  → READY (camera bound, BLE streaming)
READY → PREP(trialIdx)     (3s countdown, TTS speaks prompt)
PREP  → RECORDING(trialIdx) (start CameraX VideoCapture, start IMU buffer)
RECORDING → CONFIRM(trialIdx, recording) (auto after estimatedDuration; STOP camera + flush IMU to file)
CONFIRM → READY (advance trialIdx)
CONFIRM → PREP (redo current)
RECORDING → PAUSED (user tapped ⏸)
PAUSED → RECORDING (resume; record gets a "pause-mark" in JSON)
any → ERROR (BLE drop, camera fail) → recoverable or terminal
```

**Widgets** (top-to-bottom):
- **Top bar**: subject ID + protocol name + "$current / $total". `LinearProgressIndicator` showing fraction. Back button shows confirm dialog "Exit session? You'll go to Review." Replace plain back with explicit `IconButton(close)` — user must consciously exit.
- **Prompt card** (large): centered word in 80sp monospace bold; below it the letter-by-letter view (e.g. `C · A · T`); below that a small "hint" line from `TrialDef.hint`.
- **State indicator**: dot row `●●●` animated during recording; `3...2...1` digits during PREP; check ✓ during CONFIRM.
- **Camera preview** (`AndroidView` wrapping `PreviewView`): ~25% screen height, aspect 16:9 letterboxed; bottom-left small badge "REC ●" when recording.
- **Live IMU mini-chart** (Vico LineChart, last 1s, ~80dp tall, 3 traces): thumb, index, middle norms. Updates at 20 Hz max.
- **Bottom button bar** (state-dependent):
  - In PREP: `⏯ Skip prep` (start recording immediately).
  - In RECORDING: `⏸ Pause`, `⏹ Stop early`, `✗ Cancel trial`.
  - In CONFIRM: `🔄 Redo`, `✓ Accept & Next`, `⏭ Skip`.

**Per-trial file lifecycle**:
1. On RECORDING entry: open `{sessionRoot}/trial_$NNN.mp4` via CameraX `VideoCapture.Output.FileOutputOptions`. Start IMU collection (clear buffer, set `collecting=true`).
2. On RECORDING exit (timer or user stop): stop camera (await `VideoRecordEvent.Finalize`), stop IMU collection, snapshot buffer.
3. Serialize JSON → write to `{sessionRoot}/trial_$NNN.json` (atomic: write to `.tmp`, fsync, rename).
4. Insert `RecordingEntity` row (`accepted = true` provisional; updated to user choice on CONFIRM).
5. On CONFIRM redo: delete the just-written file pair, decrement orderInSession, return to PREP.

**Key invariants**:
- The IMU `raw_data` array is built from `TapStrapClient.packets()` filtered by `collecting=true && type in {accl, imu}` and timestamped with `recv_time = System.currentTimeMillis() / 1000.0`.
- `Recording.startedAt` = wall-clock at RECORDING entry (ms). `endedAt` = at exit. `collect_time` in JSON = (endedAt - startedAt) / 1000.0.

**Actions**:
- ⏸ Pause: stop video, stop IMU collection, freeze timer. Resume button appears. Pause does NOT redo; it continues the same trial. **Note**: CameraX `Recording.pause()` exists; for IMU we just drop a marker packet `{"type":"_pause","ts":wall,"recv_time":wall}` into the buffer.
- 🔄 Redo: deletes current trial files, returns to PREP for same trial; increments `RecordingEntity.redoCount`.
- ✗ Skip: writes a `Recording` row with `accepted=false, signalNote="skipped"`, advances.
- ⏭ Prev: only in CONFIRM and only if trialIdx>0; lets researcher fix the prior trial.

**Audio prompts (TTS)**:
- On PREP entry: `tts.speak("Please spell ${word}")`.
- 3-2-1 countdown: short beep (low pitch) each second, higher pitch beep on RECORDING entry, double beep on RECORDING exit. Use `SoundPool` (pre-loaded tones in `res/raw/`), not the system Tink sound.

**Nav out**:
- Auto on completion of last trial → `Routes.sessionReview(sessionId)` with `popUpTo(HOME)`.
- Manual back → confirm → `Routes.sessionReview(sessionId)` (still review the partial data).

**Reads**: trial list from arguments, `TapStrapClient.packets()`, prefs (TTS rate, beep on/off, video on/off).

**Writes**: `RecordingDao.upsert()` per trial; `SessionDao.update()` on each trial completion (incremental `maxAcclChannelsSeen = maxOf(...)`); files to disk.

**Validation / runtime checks**:
- If BLE drops mid-RECORDING → enter ERROR state, pause timer, show banner "Tap Strap disconnected — reconnect to continue". On reconnect → user choice: "Resume trial (data so far)" or "Redo trial".
- If camera fails to start → graceful degrade: show toast "Camera unavailable — proceeding without video", continue with IMU only; the per-trial JSON gets `videoMp4Path = null`.
- If storage runs low (<200 MB available, check via `StatFs` at session start and after every 10 trials) → show modal "Storage almost full. Save and exit?".

**Implementation status**: ❌ Most complex; entirely missing. Estimate 4-5 days.

---

### Screen 9 — Session Review

**Purpose**: Per-trial QA after the session ends; final accept/reject; commit or discard.

**States**:
- Loading: counting files.
- Populated.
- Saving / discarding (with progress for discard).

**Widgets**:
- `TopAppBar("Session Review", back)` — back triggers "Save with current marks?" dialog.
- Header `Card`: session info (subject, protocol, start/end, duration, trial count summary `"18 good · 1 redo · 1 skipped"`).
- `LazyColumn` of trial rows:
  - Row left: `#$n  $prompt`, status icon, duration, packet count.
  - Row right: `ImageView` for video thumbnail (extracted at 0.5s via `MediaMetadataRetriever`).
  - Action chips: ✓ Accept | ✗ Reject | ↻ Retake.
- Bottom action bar: `OutlinedButton("Discard all")` (red) + `Button("Save & Finish")` (primary).

**Actions**:
- Tap thumbnail → bottom-sheet video player (`ExoPlayer` or `androidx.media3.ui.PlayerView`) with overlay IMU plot (Vico) of the same trial.
- Accept/Reject toggles `Recording.accepted`.
- Retake → returns to Active Collection with `startTrialIdx = thisTrialIdx`; this is **non-trivial** (Active Collection must accept a "single-trial mode" argument).
- Save & Finish → `SessionDao.update(s.copy(completed=true, endedAt=now))` → `nav.navigate(Home) { popUpTo(HOME) { inclusive = true } }`.
- Discard all → confirm twice ("This deletes 20 trials, ~50 MB. Confirm?") → delete files + session row (cascades recordings) → Home.

**Nav out**: ActiveCollection(8) for retake; Home.

**Reads**: `SessionDao.byId()`, `RecordingDao.observeBySession()`, file system for thumbnails.

**Writes**: `RecordingDao.update()` (accept flag), `SessionDao.update()` (completed flag), file deletions on discard.

**Implementation status**: ❌.

---

### Screen 10 — Sessions List

**Purpose**: Library browse of all past sessions.

**States**: empty (no sessions yet), populated, filtered (empty after filter — distinct copy).

**Widgets**:
- `TopAppBar("Sessions", back, action: filter icon)`.
- Filter row (chips, expandable): subject, protocol, date range. Default: all.
- Section headers by date bucket: "Today", "Yesterday", "This week", "Earlier".
- Row: subject/protocol, time, "$completedTrials/$targetTrials", size on disk.
- Footer: "Total: N sessions · X.X GB".

**Actions**:
- Tap row → SessionDetail(11).
- Long-press → delete confirm (warns about file deletion size).
- Filter chips → live-filter the list.

**Nav out**: SessionDetail(11).

**Reads**: `SessionDao.observeAll()` (with subject/protocol joins for display) + file-system size aggregation.

**Writes**: delete sessions + cascade files.

**Empty copy**: "No sessions yet. Go to Home and tap **Start New Session**."

**Implementation status**: ❌.

---

### Screen 11 — Session Detail

**Purpose**: Read-only view of one session + entry to export/replay.

**States**: loading metadata, populated, file-missing (orphan recording row whose file was deleted manually).

**Widgets**:
- `TopAppBar("Session Detail", back, action: ⤴ Export this session)`.
- Meta card: subject, protocol, start/end/duration, device MAC + MTU + 15-channel ✓, total trials + acceptance breakdown.
- LazyColumn of trial rows (compact): `#1 CAT ✓ · 3.2s · 95 pkts`.
- Tap trial → bottom sheet with: video player, IMU plot (Vico), raw stats, file paths (copyable), "Open file in Files app" button.
- Footer: storage path (selectable text).

**Actions**: Export this session, open trial detail, copy paths.

**Nav out**: Export(12) (single-session preselect).

**Reads**: full session + recordings + file system.

**Writes**: none.

**Implementation status**: ❌.

---

### Screen 12 — Export

**Purpose**: Bundle selected sessions to a portable archive.

**States**:
- Selecting.
- Exporting (progress).
- Done (share sheet appears).
- Failed.

**Widgets**:
- `TopAppBar("Export", back)`.
- Selection card:
  - `Checkbox("All sessions (N) · X.X GB")`.
  - `Checkbox("This week (n) · …")`.
  - `Checkbox("By subject")` → expands a list of per-subject checkboxes.
  - `Checkbox("Custom selection")` → expands to full session list with per-row checkboxes.
- Format `RadioGroup`: ZIP (compressed, default) | Folder (uncompressed — staged in app cache then user picks dest via SAF).
- Destination: SAF document picker (`ACTION_CREATE_DOCUMENT` MIME `application/zip`).
- "📦 Start Export" primary button.
- `LinearProgressIndicator` during work.
- Result snackbar with "Share" action that fires `ACTION_SEND` with the ZIP URI.

**Actions**:
- Build a `WorkManager` `OneTimeWorkRequest` for the ZIP task so the app can be backgrounded during export. Show a foreground service notification with progress.
- The ZIP layout mirrors disk:
  ```
  export_20260525_1623.zip
    ├── sessions/
    │     └── {session_id}/
    │           ├── meta.json
    │           ├── trial_001.json
    │           ├── trial_001.mp4
    │           └── ...
    └── manifest.json   (export-level metadata: app version, exported_at, sessions list)
  ```

**Nav out**: back to caller.

**Reads**: selected sessions' files.

**Writes**: ZIP to user-picked URI.

**Validation**: warn if selected total > free space on destination.

**Implementation status**: ❌.

---

### Screen 13 — Settings

**Purpose**: App-wide preferences.

**Widgets** (grouped by section):
- **Collection**:
  - Default protocol dropdown.
  - Prep countdown duration (1/2/3/5 s).
  - TTS voice + rate slider.
  - "Beep on countdown" toggle.
- **Video**:
  - Resolution (720p / 1080p).
  - Camera (Back / Front).
  - FPS (30 / 60).
  - "Record audio (debug)" toggle (default OFF, see §1.8).
- **BLE**:
  - "Auto-reconnect on app start" toggle.
  - "Warn if max accl < 15" toggle.
- **Storage**:
  - Used / Free display.
  - "Open file location" → SAF picker pointed at app dir.
  - "Clear all data" (DESTRUCTIVE; triple-confirm).
- **About**:
  - Version, hardware target, paper reference.

**Reads/Writes**: `DataStore<Preferences>`.

**Implementation status**: ❌ Placeholder only.

---

## 3. Critical user flows (traced screen-by-screen)

### Flow A — First-time setup (no subjects yet)

1. App launch → MainActivity → HomeScreen.
   - State: subjectCount=0, protocolCount=4 (seeded), conn=Idle.
   - Start CTA disabled with hint "Connect Tap Strap and create a subject."
2. User taps "Device" card → DeviceSetup.
   - Permission prompt fires → grant.
   - Scan → connect → MTU 247 ✓ → "Max accl: 15 ✓".
3. Back → Home. Device card now green. Start still disabled (no subject).
4. User taps Subjects card → SubjectsList → EmptyState "No subjects yet" → tap "+ Add subject".
5. SubjectEditor (new). ID prefilled "S001". User fills name, picks Right, checks consent, taps Save.
6. Back to SubjectsList showing 1 subject. Back to Home.
7. Start CTA now enabled. (See Flow B.)

### Flow B — Full collection session

1. Home → "Start New Session" → SessionSetup.
2. Subject "S001" pre-selected (only one). Protocol: pick "Confusion Words (20 trials)". Subset: all. Options: video ON, TTS ON, beep ON.
3. Camera permission requested (first time) → grant.
4. "▶ Start Session" tapped.
   - `SessionEntity` created and inserted: id=`20260525_142312`, targetTrialsCount=20, startedAt=now, completed=false.
   - Foreground service started.
   - Navigate to Collect, popping SessionSetup from back-stack.
5. CollectScreen for trial 1 (CAT).
   - PREP: TTS speaks "Please spell CAT". 3-2-1 beeps. Prompt card animates.
   - RECORDING: VideoCapture starts (`trial_001.mp4`). IMU buffer fills. Live waveform animates.
   - At T=4s, auto-transition to CONFIRM. `trial_001.json` written. `RecordingEntity` inserted (provisional accepted=true).
   - Researcher taps ✓ Accept & Next.
6. Loop 5 → for trials 2–20. On trial 8, researcher taps 🔄 Redo. The trial_008 files are deleted, redoCount++, return to PREP.
7. After trial 20 CONFIRM → auto-navigate to SessionReview with `popUpTo(HOME)`.
8. SessionReview shows 20 rows. Researcher plays trial 8 video — looks fine. Taps Save & Finish.
   - `SessionEntity.completed=true, endedAt=now` written.
   - Navigate Home.

### Flow C — Recovery after crash mid-session

Assume crash during trial 11 RECORDING:
- `trial_011.mp4` exists but is partial (CameraX `Finalize` never fired).
- `trial_011.json` does NOT exist (we write atomically after recording stops).
- `RecordingEntity` for trial 11 does NOT exist.
- `SessionEntity` exists with `completed=false, endedAt=null`.

On app restart:
1. MainActivity / HomeScreen detects an incomplete session via `SessionDao.findIncomplete()` (`completed=false AND endedAt IS NULL AND startedAt > now - 24h`).
2. Show modal: "Resume incomplete session from 14:23? 10 trials saved."
   - "Resume" → enters Active Collection at trial 11 (re-reads protocol trial list, skips first 10 by RecordingDao count).
   - "Discard" → marks session completed=true with endedAt=now and a `signalNote="abandoned_recovery"`. Files kept (in case researcher wants them later).
   - "Review what's saved" → goes to SessionReview.
3. The orphan `trial_011.mp4` is detected on Collect-screen mount and deleted with a snackbar "Removed corrupt video from previous run".

### Flow D — Multi-subject day (5 subjects back-to-back)

Optimization needs:
- "Quick switch subject" on SessionSetup: a "New subject from here" link that opens SubjectEditor as a bottom sheet rather than full nav, returns to SessionSetup with new subject preselected.
- Settings prefs `lastSubjectId` cleared between subjects (or a "remember last" toggle).
- After each Save & Finish, Home shows snackbar "Saved. 7 sessions today · 1.2 GB used. Storage healthy." with "Start next" CTA.

### Flow E — Export to Mac

1. Sessions list → select 1 (or filter by today).
2. (Long-press → multi-select mode is overkill for MVP; use SessionDetail → Export single, or Export(12) screen with checkboxes.)
3. Export → choose ZIP → SAF picks `/Downloads/tapstrap_export.zip` → progress.
4. Connect phone to Mac via USB-C → Mac sees phone in MTP. Drag ZIP to `~/research/finger/tapstrap/data/android_imports/`.
5. On Mac: `unzip tapstrap_export.zip -d ./` → run modified `prepare_finetune_data.py --android-layout` (see §1.1) → `.npy` files appear in `/processed/`.

---

## 4. Edge cases & failure modes

| # | Scenario | Behavior |
|---|---|---|
| 1 | BLE disconnect mid-trial | Pause timer, banner "Tap Strap disconnected", auto-attempt reconnect 3x with backoff, on success user chooses resume/redo. Mark `Recording.signalNote = "ble_drop@2.3s"`. |
| 2 | BLE disconnect between trials | Banner "Reconnecting...". Block Next button until reconnected. |
| 3 | Camera permission denied | If denied at Session Setup: gray out "Record video" toggle, force OFF, banner "Camera permission denied — IMU-only mode". Session proceeds without MP4 files. |
| 4 | Storage full during session | StatFs probe before each PREP. If <100 MB, modal "Storage critical (X MB left)" → "Stop after this trial" / "Stop now" / "Continue (may fail)". |
| 5 | Force-close during trial | See Flow C. Orphan MP4 deleted on next launch. |
| 6 | Tap Strap battery dies | RSSI / GATT disconnect with status=8 (link supervision timeout). Same as #1. After 3 retry failures: modal "Battery may be low — please recharge Tap Strap." |
| 7 | Multiple Tap Straps in range | Spike picks the first BLE result whose name contains "Tap". Improve: ScanScreen modal listing all Tap-named devices with RSSI; user picks one. Cache MAC in DataStore (`preferredDeviceMac`) for auto-reconnect. |
| 8 | Phone rotation during Collect | Locked to portrait per §1.7. |
| 9 | App backgrounded during Collect | Foreground service keeps BLE + camera alive. Persistent notification. On return, ViewModel re-binds to service state. |
| 10 | Phone screen times out | `keepScreenOn = true` on Collect screen (`Modifier.systemBarsPadding` + `LocalView.current.keepScreenOn = true`). |
| 11 | TTS engine missing | Catch `TextToSpeech` init failure → silent fallback, no crash. Setting "TTS unavailable on this device". |
| 12 | User taps Start twice rapidly | Debounce: VM's `isCreatingSession` flag disables button until SessionEntity inserted. |
| 13 | DB migration on app upgrade | Use Room `fallbackToDestructiveMigration` ONLY in debug builds. For release: explicit migrations. v1 schema is the source of truth. |
| 14 | Two protocols with same name | Treat names as display-only; ID is primary key. Editor validation warns but allows. |
| 15 | Built-in protocol with stale data after seeding bug | Add a `schemaVersion` int column to ProtocolEntity (`schemaVersion = 1`). On app upgrade, if asset JSON has higher version, delete & reseed that protocol. |
| 16 | Video MP4 corrupted (Finalize race) | On SessionReview load: probe each MP4 with `MediaMetadataRetriever`; if it throws, show row marker "Video corrupt", allow accept/reject but mark `Recording.signalNote += "video_corrupt"`. |
| 17 | Trial's expectedLetters contains spaces or punctuation | TrialDef editor strips/validates to A-Z0-9 only at save time. |

---

## 5. Deliverables checklist (file-by-file build order)

Legend: ✅ done, 🟡 partial, ❌ missing.

### Phase 1 — Foundation (3–4 days)

- ✅ `build.gradle` (root + app) — already has Compose, Hilt, Room, CameraX, Vico, Serialization.
- ✅ `AndroidManifest.xml` — BLE, Camera, Audio permissions. **Edit**: remove `RECORD_AUDIO`; add `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_CONNECTED_DEVICE`, `FOREGROUND_SERVICE_CAMERA`.
- ✅ `TapStrapApp.kt` (Hilt entry).
- ✅ `MainActivity.kt` + `NavGraph.kt`.
- ✅ `data/db/{Entities, Daos, AppDatabase}.kt` — entities match spec.
- 🟡 `data/db/AppDatabase.kt` — needs `Callback.onCreate` to seed builtin protocols from assets.
- ✅ `data/ble/TapStrapClient.kt` — works.
- ✅ `data/parser/RawParser.kt` — works.
- ✅ `ui/screens/home/{HomeScreen, HomeViewModel}.kt` — done; just add disabled-state hint.
- ✅ `ui/screens/device/{DeviceSetupScreen, DeviceViewModel}.kt` — add waveform card + test-trial button + scan timeout.
- ❌ `ui/components/{EmptyState, ErrorBanner, LoadingState, WaveformChart}.kt`.
- ❌ `di/AppModule.kt` — must provide DAOs + AppDatabase (need to verify spike already does this).
- ❌ `data/store/Prefs.kt` — DataStore wrappers.

### Phase 2 — CRUD (2–3 days)

- ❌ `data/repository/{SubjectRepo, ProtocolRepo}.kt`.
- ❌ `ui/screens/subjects/SubjectListScreen.kt` (replace placeholder).
- ❌ `ui/screens/subjects/SubjectEditorScreen.kt`.
- ❌ `ui/screens/subjects/SubjectViewModel.kt`.
- ❌ `ui/screens/protocols/ProtocolListScreen.kt`.
- ❌ `ui/screens/protocols/ProtocolEditorScreen.kt`.
- ❌ `ui/screens/protocols/TrialEditorBottomSheet.kt`.
- ❌ `ui/screens/protocols/ProtocolViewModel.kt`.
- ❌ `app/src/main/assets/builtin_protocols/{asl_alphabet, asl_digits, confusion_words, all_words}.json`.
- ❌ `scripts/export_builtin_protocols.py` (Mac-side one-shot).
- ❌ `data/seed/ProtocolSeeder.kt`.

### Phase 3 — Capture core (5–7 days)

- ❌ `data/video/CameraRecorder.kt` (CameraX wrapper).
- ❌ `data/tts/PromptSpeaker.kt`.
- ❌ `data/audio/Beeper.kt` (SoundPool).
- ❌ `data/storage/SessionWriter.kt` (JSON serialize, Mac-compatible).
- ❌ `data/repository/SessionRepo.kt`.
- ❌ `service/CollectionService.kt` (LifecycleService, foreground).
- ❌ `ui/screens/session/setup/SessionSetupScreen.kt` (real impl).
- ❌ `ui/screens/session/setup/SessionSetupViewModel.kt`.
- ❌ `ui/screens/session/collect/CollectScreen.kt`.
- ❌ `ui/screens/session/collect/CollectViewModel.kt`.
- ❌ `ui/screens/session/collect/CollectStateMachine.kt`.
- ❌ `ui/screens/session/review/ReviewScreen.kt`.
- ❌ `ui/screens/session/review/ReviewViewModel.kt`.
- ❌ `res/raw/beep_low.wav`, `beep_high.wav`, `beep_done.wav`.

### Phase 4 — Library + Export (2–3 days)

- ❌ `ui/screens/library/SessionListScreen.kt` (real).
- ❌ `ui/screens/library/SessionDetailScreen.kt`.
- ❌ `ui/screens/library/SessionLibraryViewModel.kt`.
- ❌ `data/storage/Exporter.kt` (ZIP via WorkManager).
- ❌ `ui/screens/export/ExportScreen.kt`.
- ❌ `ui/screens/export/ExportViewModel.kt`.

### Phase 5 — Polish (2–3 days)

- ❌ `ui/screens/settings/SettingsScreen.kt` (real).
- ❌ `ui/screens/recovery/RecoveryPromptDialog.kt`.
- ❌ Crash analytics (optional — could use Firebase Crashlytics OR ship without).
- ❌ Add `assets/consent_en.txt` (or load from URL).
- ❌ Storage warning logic + low-space modal.
- ❌ Update Mac `prepare_finetune_data.py` to handle Android per-trial layout.

### Sequencing dependencies

- Phase 1 must finish before Phase 2 (DB schema, Hilt graph).
- Phase 2 must finish before Phase 3 (Session Setup needs Subjects + Protocols).
- Phase 3's CollectionService depends on `CameraRecorder`, `SessionWriter`, `TapStrapClient` (existing) — these three can be built in parallel.
- Phase 4 depends on Phase 3 (need real sessions to list/export).
- Phase 5 can start anytime after Phase 1.

---

## 6. Module/package rename

The plan calls for renaming `spike_android` → `collection_android`. The Kotlin package is already `com.research.tapstrap` (not `tapstrapspike` despite the directory name). **Recommendation**: keep the directory name `spike_android` to avoid IDE/git pain — it's just a directory; the user-visible app id (`com.research.tapstrap`) and label (`@string/app_name`) are clean. Rename later if/when extracting to a public repo.

---

## 7. Open questions for human decision

(Items 1–10 from the original plan are retained verbatim; 11–14 are newly surfaced.)

| # | Question | Recommendation | Owner |
|---|---|---|---|
| 1 | Per-trial vs per-session JSON file layout | **Per-trial** (this spec) + adapt `prepare_finetune_data.py` | Engineering — confirm with PI |
| 2 | Foreground service for Collect | Yes, mandatory | Engineering |
| 3 | Video audio track | Disabled by default; debug toggle in Settings | Engineering |
| 4 | Recovery semantics | Modal prompt on next launch (Resume / Discard / Review) | PI |
| 5 | Built-in `all_words` (143 trials) — ship as one big protocol or split? | Ship as one; researchers will use Subset filtering | PI |
| 6 | Consent text source | Need IRB-approved text before MVP; ship placeholder + red banner until then | IRB |
| 7 | Subject ID auto-generation | Auto-suggest `S$nnn` but editable | PI confirm |
| 8 | Storage layout: include `meta.json` per session? | Yes — Mac-readable, denormalizes subject/protocol so exports are self-describing | Confirmed |
| 9 | Crash analytics | Skip for MVP; rely on adb logcat | Engineering |
| 10 | Build flavor for "Mode B" (take-home) | Out of scope; same codebase, different default Settings later | Engineering |
| 11 | **NEW**: Reorderable trial list lib | Use `composereorderable` (small dep) OR up/down arrows (no dep). Recommend arrows for MVP. | Engineering |
| 12 | **NEW**: Subject delete with sessions | Block via FK RESTRICT (current) OR allow with cascade. Recommend block; safer. | PI |
| 13 | **NEW**: Pre-trial test recording (Device Setup) | Add it — gives researchers a 10s confidence check before going live | Engineering |
| 14 | **NEW**: Background TTS engine selection | Use system default; do NOT require Google TTS install | Engineering |

---

## 8. Validation / acceptance test

End-to-end test (also doubles as MVP demo to PI):

1. Fresh APK install on Pixel 7.
2. Launch → grant BLE + Camera + Notifications.
3. Subjects: create S001 "Alice Chen" (Right, 18.5 cm, consent ✓).
4. Device Setup: scan → connect → verify MTU > 200 and 15 ch — record screenshot for paper.
5. Test-trial: record 2s discard, verify ~290 packets received.
6. Home: Start New Session → S001 + Confusion Words → 20 trials, ~7 min.
7. Complete all 20 (1 intentional redo on trial 5).
8. Session Review: play trial 5 video, accept all 20, Save & Finish.
9. Session Detail: verify storage path, copy to clipboard.
10. Export → ZIP to Downloads → connect phone via USB-C to Mac.
11. On Mac: `unzip ~/Downloads/tapstrap_export*.zip` → run updated `prepare_finetune_data.py`.
12. **PASS** if: `.npy` files generated, no parse errors, finger array shape `(T, 5, 3)`, and at least one trial has non-zero values in `finger[:, 2, 2]` (middle Z — proves the 15-channel breakthrough).

---

## Critical Files for Implementation

- `/Users/houzhen/research/paper_infocom_2027/spike_android/app/src/main/java/com/research/tapstrap/ui/screens/session/collect/CollectScreen.kt` (to be created — the core)
- `/Users/houzhen/research/paper_infocom_2027/spike_android/app/src/main/java/com/research/tapstrap/data/storage/SessionWriter.kt` (to be created — JSON Mac-compat)
- `/Users/houzhen/research/paper_infocom_2027/spike_android/app/src/main/java/com/research/tapstrap/data/video/CameraRecorder.kt` (to be created — CameraX)
- `/Users/houzhen/research/paper_infocom_2027/spike_android/app/src/main/java/com/research/tapstrap/data/db/AppDatabase.kt` (to be extended with seed callback)
- `/Users/houzhen/research/finger/tapstrap/prepare_finetune_data.py` (to be extended to read per-trial JSON layout)

---

## Concise summary (< 300 words)

**Open issues found**: 14 total requiring decision before Phase 1 freeze — 10 inherited from the original plan and 4 new (reorderable lib choice, subject-delete FK policy, pre-trial test recording, TTS engine policy). Beyond those decisions, the spec resolves 34 prior UI/copy gaps and 17 edge cases the wireframes glossed over.

**Three most consequential unresolved decisions**:
1. **Trial JSON schema**: the Mac code emits two different shapes (`gesture_id` vs `word`). I've recommended a unified `word`-shaped schema with gestures treated as 1-letter words, which requires a 5-line patch to `prepare_finetune_data.py`. PI should confirm before any data is captured.
2. **Per-trial vs per-session file layout**: I've recommended per-trial files for crash atomicity, but this changes the Mac-side ingestion contract. Needs explicit sign-off.
3. **Foreground service for Active Collection**: implicit in the original plan but not budgeted. Adds 2-3 days and a notification UX, but without it BLE + camera will die when the phone screen sleeps. This is non-negotiable for correctness.

**Spike code alignment**: The existing skeleton is structurally correct and reusable. Package layout, Room entities, DAOs, Hilt graph, BLE Flow, and the parser are all production-ready. Only minor edits needed: remove `RECORD_AUDIO` permission, add foreground-service permissions and `POST_NOTIFICATIONS`, add a `Callback.onCreate` seed step on `AppDatabase`, fix scan timeout, and lock the Collect screen to portrait. The Home and Device Setup screens are ~80% done; the other 11 screens are stubs. No restructuring required — only filling in. The dependency on the spike code's package name (`com.research.tapstrap`, not the legacy `tapstrapspike`) means no rename pain.