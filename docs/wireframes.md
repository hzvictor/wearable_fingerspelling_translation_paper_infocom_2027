# Tap Strap Collector — App Wireframes

> Paper-prototype 风格的 ASCII 线框，覆盖所有 13 屏。每屏列出：
> - 视觉布局
> - 上面有什么 widget
> - 用户能做什么 action
> - 这屏读写哪些 entity
>
> 命名 / 数据模型详见 `design.md` 和 `/Users/houzhen/.claude/plans/zippy-weaving-hummingbird.md`

---

## 🗺 导航总图

```
                  ┌──────────────┐
                  │  Home (1)    │ ← 启动入口
                  └──┬─────┬─────┘
       ┌─────────────┤     ├─────────────────────┐
       │             │     │                     │
┌──────▼───┐  ┌──────▼─┐  ┌▼──────────┐   ┌──────▼──────┐
│ Device(2)│  │Subjects│  │Protocols(5)│  │ Sessions(10) │
└──────────┘  │ (3)    │  └─┬──────────┘  └──────┬──────┘
              └──┬─────┘    │                    │
                 │          ▼                    ▼
                 ▼      ┌────────┐         ┌──────────┐
            ┌────────┐  │Editor(6)│        │ Detail(11)│
            │Editor(4)│  └────────┘         └──────────┘
            └────────┘                            │
                                                  ▼
                              ┌─────────────┐  ┌────────┐
                              │SessSetup(7) │  │Export(12)│
                              └──────┬──────┘  └────────┘
                                     ▼
                              ┌─────────────┐
                              │ Collect (8) │ ★ 核心
                              └──────┬──────┘
                                     ▼
                              ┌─────────────┐
                              │ Review (9)  │
                              └─────────────┘

                  ┌──────────────┐
                  │ Settings(13) │ ← Home 抽屉
                  └──────────────┘
```

---

## (1) Home / Dashboard

**目的**：一眼看清状态，一键进入采集

```
┌────────────────────────────────────────┐
│ ☰  TapStrap Collector                  │
├────────────────────────────────────────┤
│                                        │
│  ┌──────────────────────────────────┐  │
│  │ 📡  Device                       │  │
│  │      Connected · MAC: D2:45:..   │  │
│  │      MTU 247  · 15 channels  ✓   │  │
│  └──────────────────────────────────┘  │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │ 👥  Subjects                  8  │  │
│  │      Last: S007 · 2 hours ago    │  │
│  └──────────────────────────────────┘  │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │ 📋  Protocols                 6  │  │
│  │      ASL Alphabet · Confusion …  │  │
│  └──────────────────────────────────┘  │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │ ▶️  Sessions                 24  │  │
│  │      143 recordings · 2.1 GB     │  │
│  └──────────────────────────────────┘  │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │       ▶  Start New Session       │  │ ← Primary CTA
│  └──────────────────────────────────┘  │
│                                        │
│         ⚙ Settings                     │
└────────────────────────────────────────┘
```

**Widgets**：Material 3 Cards (4) + Filled Button + TextButton

**Actions**:
- Tap Device 卡 → DeviceSetup (2)
- Tap Subjects 卡 → SubjectsList (3)
- Tap Protocols 卡 → ProtocolsList (5)
- Tap Sessions 卡 → SessionsList (10)
- Tap "Start New Session" → SessionSetup (7)
- Tap Settings → Settings (13)

**数据读**: Device state (BLE), counts from Room (subjects, protocols, sessions)
**数据写**: 无

---

## (2) Device Setup

**目的**：连接 Tap Strap，**验证 MTU 15 通道是否成功**

```
┌────────────────────────────────────────┐
│ ←  Device                              │
├────────────────────────────────────────┤
│ ┌────────────────────────────────────┐ │
│ │ ✓ Connected: D2:45:26:5A           │ │ ← color banner
│ └────────────────────────────────────┘ │
│                                        │
│ ┌──────────────┐  ┌─────────────────┐ │
│ │Scan & Connect│  │   Disconnect    │ │
│ └──────────────┘  └─────────────────┘ │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │ KEY METRICS                        │ │
│ │                                    │ │
│ │ MTU:                  247  ✓      │ │
│ │ Max packet size:       64 B ✓     │ │
│ │ Max accl channels:    15   ✓ ←⭐  │ │
│ │                                    │ │
│ │ Packets received: 1,247           │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │ Live waveform (last 3s)            │ │
│ │   ╱╲    ╱╲╱╲   ╱╲                  │ │
│ │  ╱  ╲  ╱    ╲ ╱  ╲                 │ │
│ │ ╱    ╲╱      V    ╲                │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │ How to read these numbers          │ │
│ │ · MTU ≥ 37 → 15-ch pipe OK         │ │
│ │ · 15 ch = breakthrough success     │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

**Widgets**: Banner + 2 Buttons + Metrics Card + Vico Line Chart + Help Card

**Actions**:
- Scan & Connect → 触发权限 → BLE scan → 连接 → MTU 协商
- Disconnect → 断开 GATT

**数据读**: `TapStrapClient.conn`, `TapStrapClient.packets()`
**数据写**: 无（live only，下游 session 才存）

---

## (3) Subjects List ⭐ CRUD-R, CRUD-D

**目的**：管理 subject 库

```
┌────────────────────────────────────────┐
│ ←  Subjects             🔍             │
├────────────────────────────────────────┤
│ ┌────────────────────────────────────┐ │
│ │ 🔍 Search subjects...               │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │ S001  Alice Chen           Right   │ │
│ │       4 sessions · last 2d ago    >│ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ S002  Bob Liu              Left    │ │
│ │       2 sessions · last 5d ago    >│ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ S003  Charlie Wang         Right   │ │
│ │       0 sessions                  >│ │
│ └────────────────────────────────────┘ │
│                                        │
│                                        │
│                              ┌───┐     │
│                              │ + │ FAB │
│                              └───┘     │
└────────────────────────────────────────┘
```

**Widgets**: TopAppBar + SearchField + LazyColumn(Card) + FAB

**Actions**:
- Tap row → SubjectEditor (4) for edit
- Long-press row → 「Delete subject?」 dialog
- Tap FAB → SubjectEditor (4) for new
- Search 实时过滤

**数据读**: `SubjectDao.observeAll()` + session count per subject
**数据写**: Delete (with confirm)

---

## (4) Subject Editor ⭐ CRUD-C, CRUD-U

**目的**：新增 / 编辑 subject 详情

```
┌────────────────────────────────────────┐
│ ←  New Subject              ✓ Save     │
├────────────────────────────────────────┤
│ ID (auto if blank)                     │
│ ┌────────────────────────────────────┐ │
│ │ S008                                │ │
│ └────────────────────────────────────┘ │
│ Display Name *                         │
│ ┌────────────────────────────────────┐ │
│ │ David Park                          │ │
│ └────────────────────────────────────┘ │
│ Dominant Hand *                        │
│   ( ) Left      (●) Right              │
│ Hand Length (cm)                       │
│ ┌────────────────────────────────────┐ │
│ │ 19.5                                │ │
│ └────────────────────────────────────┘ │
│ Age Range                              │
│ ┌────────────────────────────────────┐ │
│ │ ▼ 20-29                             │ │
│ └────────────────────────────────────┘ │
│ Gender                                 │
│ ┌────────────────────────────────────┐ │
│ │ ▼ Prefer not to say                 │ │
│ └────────────────────────────────────┘ │
│ Notes                                  │
│ ┌────────────────────────────────────┐ │
│ │ Wears glasses; tested 3/12         │ │
│ │                                     │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ☐ I have read and accept the consent  │
│   form (collected on YYYY-MM-DD HH:MM)│
│                                        │
│ ─────── Sessions for this subject ──── │
│ • 2026-05-20 · ASL Alphabet · ✓       │
│ • 2026-05-15 · Confusion Words · ✓    │
└────────────────────────────────────────┘
```

**Widgets**: TextField + RadioGroup + Dropdown + Checkbox + Read-only sessions list

**Actions**:
- ✓ Save → Room upsert → 回退到 List
- ← Back → 弃用 (with confirm 如果 dirty)
- Tap session row → 跳到 SessionDetail (11)

**数据读**: If editing: Subject by id, sessions by subjectId
**数据写**: `SubjectDao.upsert()` (含 createdAt/updatedAt/consentAt 自动)

---

## (5) Protocols List ⭐ CRUD-R, CRUD-D

**目的**：管理协议（builtin 不可改）

```
┌────────────────────────────────────────┐
│ ←  Protocols                           │
├────────────────────────────────────────┤
│ ─── Built-in ───                       │
│ ┌────────────────────────────────────┐ │
│ │ 🔒 ASL Alphabet (A-Z)              │ │
│ │    26 trials · gesture            >│ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ 🔒 ASL Digits (0-9)                │ │
│ │    10 trials · gesture            >│ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ 🔒 Confusion-pair Words            │ │
│ │    20 trials · word               >│ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ 🔒 All Words (143)                 │ │
│ │    143 trials · word              >│ │
│ └────────────────────────────────────┘ │
│                                        │
│ ─── Custom ───                         │
│ ┌────────────────────────────────────┐ │
│ │ ✎ My subset                        │ │
│ │    8 trials · word                >│ │
│ └────────────────────────────────────┘ │
│                                        │
│                              ┌───┐     │
│                              │ + │ FAB │
│                              └───┘     │
└────────────────────────────────────────┘
```

**Widgets**: TopAppBar + Section headers + LazyColumn + FAB

**Actions**:
- Tap row → ProtocolEditor (6) (builtin = read-only mode)
- Long-press custom → Delete confirm
- FAB → New protocol

**数据读**: `ProtocolDao.observeAll()`
**数据写**: Delete custom only

---

## (6) Protocol Editor ⭐ CRUD-C, CRUD-U + Trial CRUD

**目的**：编辑协议 + 增删改 trials

```
┌────────────────────────────────────────┐
│ ←  Edit: My subset           ✓ Save    │
├────────────────────────────────────────┤
│ Name *                                 │
│ ┌────────────────────────────────────┐ │
│ │ My subset                           │ │
│ └────────────────────────────────────┘ │
│ Type:  (●) word    ( ) gesture         │
│ Description                            │
│ ┌────────────────────────────────────┐ │
│ │ Subset for pilot day 3              │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ─── Trials (8) ──────────── 🔀 reorder │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │ ≡ 1.  CAT       letters: C-A-T   ✗ │ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ ≡ 2.  DOG       letters: D-O-G   ✗ │ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ ≡ 3.  HELLO     letters: H-E-...  ✗│ │
│ └────────────────────────────────────┘ │
│ ...                                    │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │  + Add trial                        │ │
│ └────────────────────────────────────┘ │
│                                        │
│ [tap trial → modal with: prompt,      │
│  expectedLetters, hint, group, dur]   │
└────────────────────────────────────────┘
```

**Widgets**: TextFields + Radio + Reorderable LazyColumn + per-row delete + Modal trial editor

**Actions**:
- ≡ 拖拽排序
- ✗ 删除单个 trial
- Tap row → modal edit
- + Add trial → modal new
- ✓ Save → Room transaction (replaceProtocolWithTrials)

**数据读**: Protocol + its trials
**数据写**: `ProtocolDao.replaceProtocolWithTrials()` (含 trials 全替换)

---

## (7) Session Setup

**目的**：选 subject + protocol + 子集 → 启动 session

```
┌────────────────────────────────────────┐
│ ←  New Session                         │
├────────────────────────────────────────┤
│ Subject *                              │
│ ┌────────────────────────────────────┐ │
│ │ ▼ S001 - Alice Chen (Right)        │ │
│ └────────────────────────────────────┘ │
│                                        │
│ Protocol *                             │
│ ┌────────────────────────────────────┐ │
│ │ ▼ Confusion-pair Words (20 trials) │ │
│ └────────────────────────────────────┘ │
│                                        │
│ Subset                                 │
│ ┌────────────────────────────────────┐ │
│ │ ☑ All groups                       │ │
│ │ ─ Or filter by group:              │ │
│ │ ☑ confusion (20)                   │ │
│ │ ☐ coarticulation (12)              │ │
│ │ ☐ common (15)                      │ │
│ └────────────────────────────────────┘ │
│                                        │
│ Options                                │
│ ☑ Record video (back camera)           │
│ ☑ TTS read prompt aloud                │
│ ☑ Beep on countdown                    │
│                                        │
│ ─────────────────────────────────────  │
│ Will run 20 trials, ~7 min             │
│                                        │
│ Device: ✓ Connected · 15 channels      │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │      ▶  Start Session              │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

**Widgets**: Dropdowns + Checkboxes + Status line + Filled Button

**Actions**:
- 选 Subject/Protocol/options
- Start → 创建 SessionEntity → 跳 CollectScreen (8)

**数据读**: All subjects, all protocols, device conn state
**数据写**: `SessionDao.upsert()` (new session with startedAt=now)

---

## (8) ⭐ CORE ⭐ Active Collection

**目的**：单 trial 提示 + 录 IMU + 录视频。**App 的灵魂**。

```
┌────────────────────────────────────────┐
│ ←  S001 / Confusion Words   3 / 20     │
│ ▓▓▓▓░░░░░░░░░░░░░░░ 15%               │
├────────────────────────────────────────┤
│                                        │
│        ┌─────────────────┐             │
│        │                 │             │
│        │      CAT        │ ← prompt    │
│        │                 │             │
│        │     C·A·T       │ ← letters   │
│        └─────────────────┘             │
│                                        │
│        ●  ●  ●                         │
│        recording • 2.3s left           │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │                                    │ │
│ │   📹 [ camera preview, small ]     │ │
│ │                                    │ │
│ └────────────────────────────────────┘ │
│                                        │
│  Live IMU                              │
│  ╱╲╱╲  ╱╲    ╱╲╱╲                     │
│  └ thumb ─ index ─ middle ┘            │
│                                        │
│ ┌──────┬──────┬──────┬──────┬──────┐  │
│ │ ⏮    │  ▶   │  🔄   │  ⏸   │  ✗  │  │
│ │ Prev │ Next │ Redo │Pause │Skip │  │
│ └──────┴──────┴──────┴──────┴──────┘  │
└────────────────────────────────────────┘
```

**状态机**：

```
   PREP (3s + TTS "Spell CAT") ──→ RECORDING (N seconds, ●●●) ──→
       ↑                                       │
       │ redo                                  │ auto / next btn
       └────────── CONFIRM (accept / redo / skip)
```

**Widgets**:
- Top bar: subject/protocol/progress
- Big prompt card (auto-scaled font)
- TTS-fired countdown indicator
- CameraX `PreviewView` (≈ 1/3 screen)
- Vico mini chart (live IMU last 1s)
- Bottom button row

**Actions**:
- ▶ Next → 完成当前 → 保存 Recording → 下一 trial
- 🔄 Redo → 重录当前 trial（redoCount++）
- ⏮ Prev → 回上一个（标记 needs-redo）
- ⏸ Pause → 暂停采集，状态保持，可恢复
- ✗ Skip → 跳过（标记 skipped）

**数据读**: 当前 trial definitions
**数据写**: 每完成 trial → `RecordingDao.upsert()` + 文件 (trial_NNN.json + trial_NNN.mp4)
后台持续：BLE 包累积 → 写入 JSON 时清空

**关键文件落地**：
```
{sessionRoot}/trial_001.json   ← 跟 Mac 格式 byte-compatible
{sessionRoot}/trial_001.mp4
{sessionRoot}/trial_002.json
...
```

---

## (9) Session Review

**目的**：session 结束后，逐 trial 复审 + 标记 + 保存/丢弃

```
┌────────────────────────────────────────┐
│ ←  Session Review                      │
├────────────────────────────────────────┤
│ S001 · Confusion Words · 20 trials     │
│ Started 14:23 · Ended 14:34            │
│                                        │
│ ─── Trials ─────────────────────────── │
│ ┌────────────────────────────────────┐ │
│ │ 1. CAT    ✓ accepted · 3.2s   ▶   │ │
│ │   thumbnail [▮▮]      [✓][✗][↻]   │ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ 2. SAT    ✓ accepted · 2.9s   ▶   │ │
│ │   thumbnail [▮▮]      [✓][✗][↻]   │ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ 3. MAT    ✓ accepted (redo×2)  ▶  │ │
│ │   thumbnail [▮▮]      [✓][✗][↻]   │ │
│ └────────────────────────────────────┘ │
│ ...                                    │
│                                        │
│ Summary: 18 good · 1 redo · 1 skipped  │
│                                        │
│ ┌──────────────┐ ┌─────────────────┐   │
│ │ Discard all  │ │ Save & Finish   │   │
│ └──────────────┘ └─────────────────┘   │
└────────────────────────────────────────┘
```

**Widgets**: Header info + LazyColumn rows with video thumbnail + ▶ play + accept/reject/retake buttons

**Actions**:
- ▶ Tap thumbnail → 全屏播视频 + 叠加 IMU 波形
- ✓ Accept / ✗ Reject / ↻ Retake (跳回 Collect with 这一 trial pre-selected)
- Save & Finish → session.completed=true → 回 Home
- Discard all → 删 session 文件夹 + Room 行

**数据读**: Session + Recordings
**数据写**: `RecordingDao.update()` (accepted flag), `SessionDao.update()` (completed)

---

## (10) Sessions List ⭐ CRUD-R, CRUD-D

**目的**：浏览历史所有 session

```
┌────────────────────────────────────────┐
│ ←  Sessions             🔍  ⚙ filter   │
├────────────────────────────────────────┤
│ Filter: [ All subjects ▼ ] [ Any ▼ ]   │
│         [ This month ▼ ]               │
│                                        │
│ ─── Today ───                          │
│ ┌────────────────────────────────────┐ │
│ │ S001 · ASL Alphabet                │ │
│ │ 14:23 · 26/26 · 5.2 MB            >│ │
│ └────────────────────────────────────┘ │
│                                        │
│ ─── Yesterday ───                      │
│ ┌────────────────────────────────────┐ │
│ │ S001 · Confusion Words             │ │
│ │ 11:05 · 18/20 · 3.8 MB            >│ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ S002 · ASL Digits                  │ │
│ │ 16:40 · 10/10 · 2.1 MB            >│ │
│ └────────────────────────────────────┘ │
│                                        │
│ ─── Earlier ───                        │
│ ...                                    │
│                                        │
│ Total: 24 sessions · 2.1 GB           │
└────────────────────────────────────────┘
```

**Widgets**: Filters + grouped LazyColumn (按日期分组)

**Actions**:
- Tap row → SessionDetail (11)
- Long-press → 「Delete? (also deletes 5.2MB of files)」
- Filter dropdowns 联动

**数据读**: `SessionDao.observeAll()` + filter
**数据写**: Delete (with confirm + file cleanup)

---

## (11) Session Detail

**目的**：单 session 元数据 + 所有 trials 详情 + 导出入口

```
┌────────────────────────────────────────┐
│ ←  Session Detail        ⤴ Export      │
├────────────────────────────────────────┤
│ ┌────────────────────────────────────┐ │
│ │ Subject:   S001 - Alice Chen       │ │
│ │ Protocol:  Confusion-pair Words    │ │
│ │ Started:   2026-05-24 14:23        │ │
│ │ Ended:     2026-05-24 14:34        │ │
│ │ Duration:  11 min 12 s             │ │
│ │ Device:    D2:45:26:5A  · MTU 247  │ │
│ │ Channels:  15 ✓                    │ │
│ │ Total:     20 trials · 18 good     │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ─── Trials ─────────────────────────── │
│ ┌────────────────────────────────────┐ │
│ │ #1 CAT    ✓ · 3.2s · 95 pkts     >│ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ #2 SAT    ✓ · 2.9s · 88 pkts     >│ │
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │
│ │ #3 MAT    ✓ (redo×2) · 4.1s      >│ │
│ └────────────────────────────────────┘ │
│ ...                                    │
│                                        │
│ Storage path:                          │
│ /Android/data/com.research.tapstrap/   │
│ files/sessions/{id}/                   │
└────────────────────────────────────────┘
```

**点 trial 进入子 sheet**：
```
┌────────────────────────────────────────┐
│ Trial 1: CAT                       ✗   │
├────────────────────────────────────────┤
│ [ Video player, ~60% screen ]          │
│                                        │
│ IMU plot (thumb / index / middle):     │
│  ╱╲    ╱╲╱╲                            │
│ ╱  ╲  ╱    ╲                           │
│                                        │
│ packets: 95 (accl 50, imu 45)         │
│ channels: 15  · duration: 3.2s        │
│ file: trial_001.json + .mp4            │
└────────────────────────────────────────┘
```

**Widgets**: Meta card + LazyColumn + bottom sheet for trial detail with `ExoPlayer` + Vico chart

**Actions**: Export, view trial detail
**数据读**: Session + recordings + file system metadata
**数据写**: 无

---

## (12) Export

**目的**：把 session 打包导出（USB MVP）

```
┌────────────────────────────────────────┐
│ ←  Export                              │
├────────────────────────────────────────┤
│ Select sessions:                       │
│ ┌────────────────────────────────────┐ │
│ │ ☑ All sessions (24)  · 2.1 GB     │ │
│ │ ☐ This week (5) · 380 MB          │ │
│ │ ☐ By subject ▼                    │ │
│ │ ☐ Custom selection ▶              │ │
│ └────────────────────────────────────┘ │
│                                        │
│ Format:                                │
│ (●) ZIP (Mac-compatible)               │
│ ( ) Folder (rsync to USB)              │
│                                        │
│ Output:                                │
│ ┌────────────────────────────────────┐ │
│ │ /Downloads/tapstrap_export_xxx.zip │ │
│ │ [Change destination]                │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │  📦  Start Export                   │ │
│ └────────────────────────────────────┘ │
│                                        │
│ [progress bar appears when running]    │
│ ▓▓▓▓▓▓░░░░  62%  · 1.3 GB / 2.1 GB    │
└────────────────────────────────────────┘
```

**Widgets**: Checkbox list + RadioGroup + path picker + Filled Button + LinearProgressIndicator

**Actions**:
- Select sessions
- Choose format
- Start Export → 后台 service 打包 → 完成提示 + 系统 Share Sheet

**数据读**: Selected sessions' files
**数据写**: ZIP 文件到 Downloads/

---

## (13) Settings

```
┌────────────────────────────────────────┐
│ ←  Settings                            │
├────────────────────────────────────────┤
│ ─── Collection ───                     │
│ Default protocol                       │
│ ┌────────────────────────────────────┐ │
│ │ ▼ Confusion-pair Words              │ │
│ └────────────────────────────────────┘ │
│ Prep countdown                         │
│ ┌────────────────────────────────────┐ │
│ │ 3 seconds                  ▼       │ │
│ └────────────────────────────────────┘ │
│ TTS voice                              │
│   ( ) System default  (●) English      │
│ TTS speech rate                        │
│   [▮▮▮▮▮▮▮▮▮◯◯◯◯]                       │
│                                        │
│ ─── Video ───                          │
│ Resolution: (●) 1080p ( ) 720p         │
│ Camera:     (●) Back   ( ) Front       │
│ FPS:        (●) 30     ( ) 60          │
│                                        │
│ ─── BLE ───                            │
│ ☑ Auto-reconnect on app start          │
│ ☑ Warn if max accl < 15                │
│                                        │
│ ─── Storage ───                        │
│ Used: 2.1 GB · Free: 47 GB             │
│ ┌────────────────────────────────────┐ │
│ │ Open file location in Files app    │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ─── About ───                          │
│ Version 0.2-mvp                        │
└────────────────────────────────────────┘
```

**数据读/写**: DataStore preferences

---

## 🔄 CRUD 速查表

| 实体 | Create | Read | Update | Delete |
|---|---|---|---|---|
| **Subject** | (4) Editor | (3) List · (4) Editor · (1) Home count | (4) Editor | (3) List long-press |
| **Protocol** | (6) Editor (custom only) | (5) List · (6) Editor · (1) Home count | (6) Editor (custom only) | (5) List long-press (custom only) |
| **TrialDef** | (6) Editor | (6) Editor (read-only for builtin) | (6) Editor | (6) Editor row ✗ |
| **Session** | (7) Setup → (8) Collect 自动 | (10) List · (11) Detail · (1) Home count | (9) Review (completed flag) · (8) Collect (期间) | (10) List long-press |
| **Recording** | (8) Collect 自动 | (9) Review · (11) Detail | (9) Review (accept/reject) | (9) Review (Discard all 整 session) |

---

## 📂 录入的数据（每个 trial）

### 物理文件
```
{sessionRoot}/
├── meta.json
│   {
│     "session_id": "20260524_142312",
│     "subject_id": "S001",
│     "subject_name": "Alice Chen",     // snapshot
│     "subject_dominant_hand": "R",     // snapshot
│     "protocol_id": "confusion_words",
│     "protocol_name": "Confusion-pair Words",
│     "device_mac": "D2:45:26:5A",
│     "negotiated_mtu": 247,
│     "max_accl_channels_seen": 15,
│     "started_at": "2026-05-24T14:23:12",
│     "ended_at": "2026-05-24T14:34:24"
│   }
│
├── trial_001.json       ← Mac 格式兼容
│   {
│     "word": "CAT",
│     "letters": ["C","A","T"],
│     "num_letters": 3,
│     "group": "confusion",
│     "confusion_test": "A/S/T/M/N",
│     "trial": 1,
│     "collect_time": 3.2,
│     "timestamp": 1779234792.123,
│     "num_packets": 95,
│     "num_accl": 50,
│     "num_imu": 45,
│     "raw_data": [
│       {"type":"accl","ts":22673,"payload":[19,-27,3,-6,9,32,-9,25,1,2,3,4,5,6,7],"recv_time":1779234792.085},
│       {"type":"imu","ts":22680,"payload":[0,0,0,16384,0,0],"recv_time":1779234792.092},
│       ...
│     ]
│   }
│
├── trial_001.mp4        ← 后摄 1080p @ 30fps，时间戳同设备时钟
├── trial_002.json
├── trial_002.mp4
└── ...
```

### Room（设备本地索引）
- 上面 5 个 entity 的所有字段

---

## 🚧 还缺什么（实施前要决定）

| # | 项 | 暂定默认 | 谁能拍 |
|---|---|---|---|
| 1 | 视频朝向 | 后摄（三脚架对手）| PI |
| 2 | 是否录前置（subject 的脸） | 否（隐私）| PI |
| 3 | 同意书完整文本 | 需 IRB 给 | IRB |
| 4 | 录视频时是否抑制提示音通过外放（影响 mic）| 是 | 工程默认 |
| 5 | App 中途 crash 恢复 | 自动 resume 到最后保存的 trial | 工程默认 |
| 6 | 多 Tap Strap 设备支持 | 只支持 1 个（够用）| — |
| 7 | 离线 TTS vs Google TTS | 离线（避免依赖网络） | 工程默认 |
| 8 | 是否做夜间模式 | 跟系统 | 工程默认 |
| 9 | 多用户登录 | 不做 | — |
| 10 | 云同步 | 不做 | — |

---

## 实施顺序提醒

- (1)(2) Home + Device 已实现（Phase 1 in progress）
- (3)(4) Subjects · (5)(6) Protocols 是 Phase 2
- (7)(8)(9) Session 三屏是 Phase 3，**(8) 最复杂、最关键**
- (10)(11) Library 是 Phase 4
- (12) Export 是 Phase 4
- (13) Settings 是 Phase 5

总工作量预估 **~2.5 周**（一个会写 Android 的人）。
