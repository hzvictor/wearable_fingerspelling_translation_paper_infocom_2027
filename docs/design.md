# INFOCOM 2027 Paper — 设计文档

> 这是工作文档，会议讨论 / 设计决策 / 待办都记在这里。

---

## 0. 投稿信息

| 项目 | 值 |
|---|---|
| 会议 | INFOCOM 2027 |
| DDL | 2026-07-31 |
| 篇幅 | 9 页正文 + 1 页 reference |
| 主题范围 | **专注手部**（指拼写 / 手势），不做 earable / 表情 |
| 基础工作 | CHASE 2026 Workshop 的 FingerSeq（4-6 页 short paper） |

---

## 1. Paper 核心问题（已锁定 2026-05-18）

> **"对于可穿戴 IMU 连续 ASL 指拼写识别，需要采集多少真实可穿戴数据用于 fine-tuning，才足以达到目标 CER？"**

### 1.1 为什么这是好问题

- ✅ **实践指导性**：直接告诉下一个研究组 / 工程团队复现这个系统的**采集预算**
- ✅ **可量化**：答案是一条数据量 → CER 曲线，加几个阈值线
- ✅ **INFOCOM 友好**：系统类审稿人最爱的 "deployment guidance" 类贡献
- ✅ **与 workshop 区分**：workshop 证明 "能做"，INFOCOM 回答 "采多少够"

### 1.2 设定（假设 / 范围）

- **Video pretrain 视为已知 prior**：用 workshop 那套 video-derived virtual IMU 预训练好的 backbone，不重新研究 pretrain 端
- **Fine-tune 数据 = 真实 Tap Strap 2 数据**：连续句子，paired (IMU, character sequence)
- **目标任务**：连续、句子级、开放词汇 ASL 指拼写识别
- **目标 CER**：暂定 20% / 15% / 14.5% 三档（14.5% ≈ workshop full fine-tune 上界）

### 1.3 故事主线（Story (ii) — Data-efficient recipe）

一句话审稿人记住的版本：

> "Without our techniques, achieving 15% CER on real wearable ASL fingerspelling requires ~**X** hours of paired data collection. With our **KD + LLM denoising** pipeline, only ~**Y** hours is sufficient — an **N×** reduction in data collection cost."

KD 和 LLM 降噪不是孤立组件，**全部挂在 "降低数据采集需求" 这条主线上**，避免拼凑感。

---

## 2. 会议记录

### 2026-05-06 会议（基于 5/5 晚 22:24–22:52 微信讨论）

**讨论要点：**
- 投稿 INFOCOM 2027，9+1 页，DDL 7/31
- 策略性提到 earable 表情识别 → 仅作参考，**不进 paper**，**专注手部**
- 待定问题：多大数据集够用
- 技术方向候选：
  - **降噪 LLM**（character sequence post-processing / 语言先验纠错）
  - **KD**（Knowledge Distillation — 跨模态 video→IMU 或模型压缩）
- 核心待量化：**自采视频 vs sensor 计算 data 的差距**
- 参考链接：https://www.sandboxaq.com/ （TODO: 确认引用哪部分工作）

### 2026-05-18 会议（已开完）

**核心决议（6 项，按 PI 在群里给的顺序）：**

1. **实验 setup + 要买的硬件清单**（需要文档化，让经费 / 采购走起来）
2. **安卓采集 App + 电脑端采集软件**（自采数据需要的工具链）
3. **论文架构先搞出来**（structure 优先于 polish）
4. **KD 降噪 LLM**（蒸馏 + 降噪两件事合一）
5. **LLM 纠错**（character sequence post-processing）
6. **🔴 fine-tuning 结果为啥不好** ← **最关键的开放问题**

**Story 确认（重要 ←）：**
- 没有正式锁，但 6 个决议合起来意味着 paper story 走 **"data-efficient recipe"**：
  - 主线：**自采数据 + KD 降噪 + LLM 纠错** = 用最少的真实采集数据训出 ASL 系统
  - "fine-tuning 为啥不好" 是 motivation/problem statement → 引出方法
  - 答案：KD + LLM 两条路降低对数据量的依赖

**未明确的，下次会议要拍：**
- [ ] 具体硬件清单（要买啥、几只、多少钱）
- [ ] 招几个 subject、采多少
- [ ] 现在的 fine-tuning 失败是数据问题 / 模型问题 / 评估问题？

---

## 3. 技术组件（候选）

| 组件 | 作用 | 状态 |
|---|---|---|
| Video-derived virtual IMU | 已有，FingerSeq 基础 | ✅ 已实现 |
| 真实 Tap Strap 数据 fine-tune | 已有 | ✅ 已实现 |
| **Sim-to-real gap 量化** | 衡量 virtual vs real IMU 分布差异 | ⬜ 新增 |
| **Domain adaptation / 缩小 gap** | adversarial / feature align / paired collection | ⬜ 新增 |
| **数据 scaling 实验** | 不同 video 数据量 → CER 曲线 | ⬜ 新增 |
| **Knowledge Distillation** | teacher (大/video) → student (小/IMU) | ⬜ 新增 |
| **LLM 降噪** | character sequence → corrected text | ⬜ 新增 |
| 完整 ablation | 各组件贡献 | ⬜ 新增 |

---

## 4. 待澄清的开放问题（按优先级）

### P0（不答无法启动实验）
1. **当前真实 Tap Strap 数据规模？** —— sentences 数、总时长、subject 数 —— 决定 scaling 曲线最右端
2. **"数据量"主轴选什么？** 推荐：**总时长（分钟/小时）** 为主轴，subject 数为辅助网格
3. **要不要做 cross-subject 切片？**（in-domain vs unseen-subject 两条曲线）—— 决定工作量是否翻倍

### P1（影响方法设计）
4. **KD 方向**：跨模态（video→IMU）or 模型压缩（大→小）or 都做 —— 推荐**跨模态**，跟主线对得上
5. **LLM 降噪具体形式**：API（GPT/Claude）或 fine-tune 小 LM 或 character-level n-gram —— 影响 on-device 论述

### P2（写作阶段再定）
6. **Baseline 范围**：自己的 CTC baseline + 无 KD/LLM 消融 是否够
7. **9 页结构与字数分配**

---

## 5. 工作分解 & 时间表

### 5.1 四条 Track

| Track | 决议项 | 性质 | 谁能并行 | 阻塞关系 |
|---|---|---|---|---|
| **A. 硬件 + 采集软件** | #1 setup/采购 + #2 安卓/PC App | 工程 | 跟 B/D 并行 | 不阻塞 |
| **B. 论文架构** | #3 架构先搞出来 | 写作 | 跟 A/D 并行 | 不阻塞 |
| **C. 方法实现** | #4 KD 降噪 + #5 LLM 纠错 | 算法 | 阻塞于 D | **必须 D 先有结论** |
| **D. 🔴 Debug fine-tuning** | #6 为啥不好 | 诊断 | — | **门控所有 C，影响 paper 主线说服力** |

### 5.2 时间表（按 2026-07-31 倒推 ≈ 9.5 周）

| 周次 | Track A | Track B | Track C | Track D |
|---|---|---|---|---|
| **W1（本周）** | 硬件清单 + 报价 | 9 页 outline 草稿 | — | 🔴 **诊断 fine-tuning 问题** |
| **W2** | 下单 + 安卓 App MVP | Intro/Related Work 文献铺 | 等 D 结论 → 定 KD 方案 | 形成结论 |
| **W3** | 设备到位 + PC 端同步 pipeline | System/Method 章节骨架 | KD 实现起步 | 验证修复 |
| **W4** | Pilot 采集 1-2 subjects | — | KD 完整实现 + 实验 | — |
| **W5** | 全量采集开始 | Methods 章节填实 | LLM 纠错实现 | — |
| **W6** | 采集完成 + 数据清洗 | — | KD + LLM 联合训练 | — |
| **W7** | — | Evaluation 章节 | 完整 ablation | — |
| **W8** | — | Discussion + Figures | 复现 + 收尾 | — |
| **W9** | — | 全文 polish + 摘要 | — | — |
| **W10** | — | 投稿 | — | — |

### 5.3 关键风险点

- **R1 (P0)：fine-tuning 不好的根因未定** → KD / LLM 都可能解决错问题。**必须 W1 解决**
- **R2 (P0)：硬件到货周期** → Tap Strap / 摄像头有 1-2 周物流，W1 必须下单
- **R3 (P1)：采集只有 W4-W6 三周** → 任何 subject 招募 / IRB 流程慢就崩
- **R4 (P1)：论文 outline 拖到方法实现完才动笔** → 经典写作崩盘模式，B Track 必须 W1 并行起来

---

## 6.0 已完成（2026-05-25）

### Android Spike App 项目已创建
位置：`/Users/houzhen/research/paper_infocom_2027/spike_android/`

包含：
- 完整 Android Studio 项目（13 个文件）
- BLE 客户端（`TapStrapClient.kt`）：scan → connect → **requestMtu(517)** → notify → 解析
- Raw 解析（`RawParser.kt`）：直接 port 自 Mac 端 `parse_raw`
- UI（`MainActivity.kt` + `activity_main.xml`）：3 关键指标实时显示（MTU / max packet / max accl channels）
- 权限配置（Android 12+ 新 BLE 权限 + 旧版兼容）
- README 详细说明

唯一目的：在真机上验证 Android 端能否从 Tap Strap 拿到 **15 通道** accl 数据（突破 macOS 8 通道天花板）。

### 现状（2026-05-25 更新）
- [x] 项目代码完成
- [x] Gradle 构建验证 → `BUILD SUCCESSFUL in 4m 11s`，APK 生成
- [x] Emulator 跑通 UI（验证编译 + 启动 + 权限对话框 + 日志反馈）
- [ ] **真机 BLE 测试（用户过 2 天测）** ← 唯一未验证：Tap Strap 实际通信 + MTU 协商 + 通道数

### Emulator 验证截图
保留在 `/tmp/spike_screen{1,2,3}.png` 供参考：
- screen1: 主界面初始状态
- screen2: 权限对话框（Android 12+ Nearby devices）
- screen3: 拒绝权限后的错误处理日志

## 6. 本周（W1）必须落地的事

按时间紧迫度排：

### 🔴 D-1：fine-tuning 诊断（**结果已找到，下面是诊断结论**）

**位置**：`finger/docs/experiment/tapstrap_finetune_experiment.md` + `reshape_bug_report.md`

**失败模式（不是 bug，是数据不够）**：

| 设置 | Seen CER | Unseen CER |
|---|---|---|
| Scratch | 22.22% | **64.91%** |
| Scratch + Aug + 合成 | 17.78% | (进行中) |
| Virtual+FT (1st round, reshape bug 期) | 58.67% | — |

**根因**（已确认，不需要再 debug 代码）：
1. **样本量太小**：1006（312 word + 694 gesture），无法学字符级 open-vocab 泛化
2. **单 subject**：无跨人 generalization 基础
3. **字母 u 缺失**：gesture 没采，含 u 的词无法合成
4. **seen 测试词 40/41 在训练里**：seen 评估虚高，不反映真实部署
5. **历史 reshape bug 已修复**（2026-04-02），workshop 报告的旧数字需重新核对

**这把"fine-tuning 不好"翻译成了 INFOCOM paper 的 motivation**：
> "Open-vocab unseen-word CER 64.91% 证明现有数据规模不足。需要回答：
> (a) 多少真实数据 + 多少 subject 才能把 unseen CER 压到 < 20%？
> (b) KD + LLM 纠错能把这个数据需求降多少倍？"

**deliverable（已部分完成）**：本节即为诊断结论；下一步是 §6.x 的执行

### 🟡 A-1：硬件清单文档
- Tap Strap 2 数量 + 单价
- Android 手机型号（用作采集端）+ 数量
- 摄像头（同步要求：60fps + 时间戳）
- 三脚架 / 灯光 / 同步装置
- 标注 / 录制场地
- **deliverable**：一份采购单 + 总预算

### 🟡 A-2：安卓采集 App 需求文档
- 通过蓝牙读 Tap Strap → 写文件
- 与视频同步（用屏幕闪光 / 时间戳）
- 实时 sanity check（显示加速度波形）
- **deliverable**：spec 文档 + 谁开发

### 🟡 B-1：9 页 outline 草稿
- Section 标题 + 每节预计字数 + 关键 figure
- 标记 "数据待补" 的占位
- **deliverable**：design.md 新增 §7 或独立 outline.md
