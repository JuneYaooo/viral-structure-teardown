# 评测（Evals）

本目录保存 viral-structure-teardown 的行为证据：题集、量表、运行协议、真实产物与逐题判断。

## 当前版本：V2（2026-11-02，v0.3.0）

V2 针对本轮外部调研发现的逻辑问题（清单见 [iteration_notes.md](iteration_notes.md) 迭代 6），
用**同一输入**分别跑 v0.2.0（基线，git 提交 266ad86）与 v0.3.0：

| 条件 | 用例 | 通过 | 硬失败 | 通过率 95% Wilson 区间 |
| --- | --- | --- | --- | --- |
| baseline v0.2.0 | 7 | 0 | 0 | 0–35.4% |
| skill v0.3.0 | 7 | 7 | 0 | 64.6–100% |

| 用例 | 输入 | v0.2.0 | v0.3.0 |
| --- | --- | --- | --- |
| c10 真实 Whisper VTT | CC BY-SA 维基有声条目前 90 秒 | 当纯文本解析，26 块、正文混入时间码 | VTT，31 条字幕 → 17 块 |
| c11 真实 Whisper SRT | 同一音频，无标点、字幕条间隔 0 | 5 块，最长 23.0s | 17 块，最长 6.0s |
| c12 同条多句 | multi_sentence_cue_v1.srt | 14 块中 8 块 0 时长 | 0 块 0 时长 |
| c13 Netflix 式稀疏标点 | sparse_punct_netflix_style_v1.srt | 3 块（最长 24.6s），边界错位 6，例句 2/4 | 11 块（最长 5.9s），错位 0，例句 4/4 |
| c14 落点 | flat-notwist-v1 × 90s / 30s | 四段窗口两两重叠，钩子 0–13.1s，无外推提示 | 首尾相接中位落点，钩子 0–6.5s，外推/冷启动提示 |
| c15 标注一致性 | double_twist 两份标注 | 无法度量 | kappa 0.896、边界 F1 1.00、WindowDiff 0.154 |
| c16 开场钩子与语速 | 8 张拆解卡 | 无此维度 | 每卡有钩子行与段语速，仅描述 |

- 题集 [cases_v2.jsonl](cases_v2.jsonl) · 量表 [rubric_v2.md](rubric_v2.md) · 协议 [protocol_v2.json](protocol_v2.json)
- 逐题判断 [judgments_v2.jsonl](judgments_v2.jsonl) → 汇总 [summary_v2.json](summary_v2.json)（由 [scripts/aggregate_results.py](scripts/aggregate_results.py) 复算）
- 产物：当前版本 [runs_v2/](runs_v2/)，基线 [runs_v2/before_v0.2.0/](runs_v2/before_v0.2.0/)；一键复现 [scripts/run_v2.py](scripts/run_v2.py)（连跑两次 sha256 一致）
- 真实输入只存统计量：[runs_v2/real_whisper_stats.json](runs_v2/real_whisper_stats.json)

**怎么读这组数字**：V2 用例是实现改动的同一 Agent 针对本轮修复的问题设计的，基线必然失败；
它证明这些问题在同一输入上被修复，不代表整体质量提升了多少。判定为 model_only，未经独立人工复核。

### 回归

V1 的 9 个用例（c1–c9）在 v0.3.0 下重跑并逐项机械核对：段位、占比、例句命中、坏时间轴 exit 3
拦截、无标点 txt 40/40/38、模板蒸馏全部复现；句末标点充足的 6 条夹具句块逐字段与 v0.2.0 一致。
拆解卡因新增「语速」列与「开场钩子」行，sha256 变化（e8b80c7e… → bbc72319…），同版本两次渲染仍一致。

## 历史：V1（2026-09-19，v0.1.0）

9/9 通过、0 硬失败，见 [cases_v1.jsonl](cases_v1.jsonl)、[judgments_v1.jsonl](judgments_v1.jsonl)、
[summary_v1.json](summary_v1.json)、[runs_v1/](runs_v1/)。V1 产物保留原样作为历史记录，
其中的落点表与拆解卡格式已被 v0.3.0 取代。

## 评测分层

1. **脚本行为层**：对 `evals/fixtures/` 的合成夹具与真实 Whisper 输出运行四个脚本，逐条核对
   required/forbidden 原子检查。脚本全部确定性。
2. **Agent 工作流层**：Agent 读句块 JSON 后按设计段位标注、提取例句，经 annotate.py 校验；
   夹具设计段位公开在 [fixtures/README.md](fixtures/README.md)，可逐段机械核对。

## 已知限制

- 真实输入只覆盖解析层，且是朗读体维基条目而非爆款口播；YouTube 需要登录、B 站返回 HTTP 412，未取得真实爆款稿。
- 5 个模板仍由 1–2 张合成卡支撑（冷启动）。
- 一致性用例的第二份标注由 Claude Opus 5.5 撰写，撰写前看过设计段位，不是盲标。
- 全部判定为开发 Agent 自评，未独立人工复核。

## 复现

命令与参数见 [docs/usage.md](../docs/usage.md)；脚本层离线运行，无需任何 API 密钥。
