# 使用与维护文档

## 安装

把整个仓库目录放进 Agent 的 Skills 目录即可（不要只拷 SKILL.md）。仓库根目录的
`install_as_skill.sh` 会把仓库复制到 `${CODEX_HOME:-~/.codex}/skills/viral-structure-teardown`，
也可以传入目标目录作为第一个参数；已存在的旧版本会被改名备份。脚本只依赖 Python 3.10+ 标准库。

## 命令

```bash
# 1. 解析转写稿（SRT / WebVTT / 纯文本）→ 句块 JSON
python3 scripts/parse_transcript.py 转写稿.srt -o blocks.json

# 2. 校验 Agent 标注并渲染拆解卡
python3 scripts/annotate.py blocks.json annotation.json -o 拆解卡.md --json 拆解卡.json

# 3. （可选）比较两份标注的一致性
python3 scripts/agreement.py blocks.json 标注A.json 标注B.json -o 一致性.md --json 一致性.json

# 4. 蒸馏 / 检索 / 套用模板
python3 scripts/templates.py distill 卡1.json 卡2.json --template-id twist-fourpart-v1 --name 标准四段反转体 --genres 好物测评
python3 scripts/templates.py list
python3 scripts/templates.py show twist-fourpart-v1
python3 scripts/templates.py apply twist-fourpart-v1 --duration 90
```

## parse_transcript.py

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `transcript`（位置参数） | 必填 | .srt、.vtt（或首行为 WEBVTT 的文件）、纯文本 .txt |
| `-o, --output` | 打印到 stdout | 句块 JSON 输出路径 |
| `--pause-gap` | 0.5 | 字幕条边界切块的停顿阈值（秒） |
| `--max-chars` | 32 | 字幕条边界切块的单块字数上限 |
| `--max-block-s` | 6.0 | 字幕条边界切块的单块时长上限（秒） |

切块规则：

1. 至少一半字幕条带标点、且出现过终止标点（。！？!?；;…）→ 按终止标点切句；同一字幕条内的
   多句按字数比例插值起止时间。
2. 否则（标点稀疏或没有标点）→ 只在字幕条边界切：间隔 ≥ 0.5s、上一条以终止标点结尾、
   并入下一条后超过 32 字或 6 秒。单条字幕本身超限时保留原样（没有字级时间戳可细切）。
3. 纯文本：有终止标点按句切，否则按 40 字定长切（timed=false，不能做时间轴标注）。

阈值出处：0.5s 来自 Netflix 字幕时间轴规范（字幕间隔要么 2 帧要么 ≥ 半秒）；32 字来自 Netflix
简中规范每行 16 字 × 2 行；6 秒来自 TikTok 官方「钩子优先放在前 6 秒」。详见
[references/benchmarks.md](../references/benchmarks.md)。语速快、停顿短的稿子可调小 `--pause-gap`。

WebVTT：忽略 WEBVTT 头、NOTE/STYLE/REGION 块、cue 设置（align: 等）与行内标签（`<c>`、`<v>`、
时间戳标签）；时间戳小时位可省略。SRT 的 `{\an8}` 等标签同样去掉。字幕条按开始时间重排，
相邻字幕条首行与上一条末行相同（滚动字幕）时去重，时间重叠的条数写进 diagnostics 并在摘要行提示。

## annotate.py

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `blocks`（位置参数） | 必填 | parse_transcript.py 产出的句块 JSON |
| `annotation`（位置参数） | 必填 | Agent 标注 JSON（schema 见 references/structure-schema.md） |
| `-o, --output` | 打印到 stdout | 拆解卡 Markdown 输出路径 |
| `--json` | 不输出 | 结构化 JSON（供 templates.py distill 聚合） |

校验项：时间轴合法（end>start、无重叠、单调、范围内，违反则 exit 3）、覆盖率与未覆盖区间
（< 60% 提示，经验值）、四段齐缺、边界对齐（切开句块处列出）、例句命中（NFKC 后去空白与标点，
按所标时间段核对）。描述项：开场钩子（首段是否为从第一句起的钩子、首个钩子起止秒，对照
TikTok 3/6 秒建议）、段语速与全片语速（字/秒）。描述项不判对错、不打分。

## agreement.py

| 参数 | 说明 |
| --- | --- |
| `blocks` `annotation_a` `annotation_b` | 同一份句块与两份标注；A 作为边界参照 |
| `-o, --output` / `--json` | 报告 Markdown / JSON |

口径：每个句块按时间中点归入所在段；角色一致率与 Cohen kappa 逐句块计算；边界 P/R/F1 允许
±1 个句块；WindowDiff 窗口 k = A 的平均段长（句块数）的一半（至少 2），与 NLTK 的 Pk 默认窗口
约定一致。两份标注任一份时间轴非法则 exit 3。

## templates.py

| 子命令 | 说明 |
| --- | --- |
| `distill 卡… --template-id ID --name 名 [--genres 逗号分隔] [--created 日期]` | 多张拆解卡聚合为模板，写入 `--library` 目录（默认 templates/）的 `<id>.json` 与 `<id>.md` |
| `list` | 列出模板库全部模板 |
| `show ID` | 查看单个模板 |
| `apply ID --duration 秒 [-o 输出.md] [--json 输出.json]` | 中位数落点 + 观测范围；钩子终点取 min(样本绝对秒, 占比换算)；外推 / 冷启动提示 |

`--library` 可放在主命令或子命令之后，默认 `templates/`。v0.2.0 蒸馏的旧模板没有中位数统计，
apply 会退回包络换算并提示重新蒸馏。

## 退出码（四个脚本一致）

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功（annotate 的警示项、apply 的提示不算失败） |
| 2 | 输入文件不存在 / 模板不存在 |
| 3 | 校验失败或格式错误（stderr 给中文原因；annotate 不产出半成品卡片） |

## 测试与评测

```bash
python3 -m unittest discover tests      # 90 项单元测试
python3 evals/scripts/run_v2.py         # 复现 V2 评测产物（基线 v0.2.0 取自 git 提交 266ad86）
python3 evals/scripts/run_v2.py --real-dir <目录>   # 另跑真实 Whisper 输出（目录内放 real.srt / real.vtt）
python3 evals/scripts/aggregate_results.py evals/judgments_v2.jsonl --output evals/summary_v2.json
```

真实输入的生成方式（不入库）：从 Wikimedia Commons 下载 `Zh-规则怪谈.ogg`（CC BY-SA 4.0），
`ffmpeg -i Zh-规则怪谈.ogg -t 90 -ac 1 -ar 16000 clip.wav`，再
`whisper clip.wav --model small --language zh --output_format all --fp16 False`，
把输出的 .srt / .vtt 改名为 real.srt / real.vtt。

完整评测流程与证据见 [evals/README.md](../evals/README.md)。
