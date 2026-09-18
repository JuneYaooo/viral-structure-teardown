# 使用与维护文档

## 命令

```bash
# 1. 解析转写稿（SRT 或纯文本）→ 句块 JSON
python3 scripts/parse_transcript.py 转写稿.srt -o blocks.json

# 2. 校验 Agent 标注并渲染拆解卡
python3 scripts/annotate.py blocks.json annotation.json -o 拆解卡.md --json 拆解卡.json

# 3. 蒸馏 / 检索 / 套用模板
python3 scripts/templates.py distill 卡1.json 卡2.json --template-id twist-fourpart-v1 --name 标准四段反转体 --genres 好物测评
python3 scripts/templates.py list
python3 scripts/templates.py show twist-fourpart-v1
python3 scripts/templates.py apply twist-fourpart-v1 --duration 90
```

## parse_transcript.py

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `transcript`（位置参数） | 必填 | .srt 或纯文本（.txt） |
| `-o, --output` | 打印到 stdout | 句块 JSON 输出路径 |

切块规则：有终止标点（。！？!?；;…）按句切；SRT 无标点按 >0.8s 停顿切（单块超 60 字
在字幕条边界强制切）；纯文本无标点按 40 字定长切（timed=false，无法做时间轴标注）。

## annotate.py

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `blocks`（位置参数） | 必填 | parse_transcript.py 产出的句块 JSON |
| `annotation`（位置参数） | 必填 | Agent 标注 JSON（schema 见 references/structure-schema.md） |
| `-o, --output` | 打印到 stdout | 拆解卡 Markdown 输出路径 |
| `--json` | 不输出 | 结构化 JSON（供 templates.py distill 聚合） |

校验项：时间轴合法（end>start、无重叠、单调、范围内）、覆盖率与未覆盖区间、
四段齐缺（缺段如实标注）、边界对齐（切开句块处列出）、例句命中（按所标时间段逐字
核对，去空白归一）。警示项不拦截；标注模板含 structure_note（结构总评）与可选
patterns（句式模式）。

## templates.py

| 子命令 | 说明 |
| --- | --- |
| `distill 卡… --template-id ID --name 名 [--genres 逗号分隔]` | 多张拆解卡聚合为模板，写入 `--library` 目录（默认 templates/）的 `<id>.json` 与 `<id>.md` |
| `list` | 列出模板库全部模板 |
| `show ID` | 查看单个模板 |
| `apply ID --duration 秒 [-o 输出.md] [--json 输出.json]` | 占比区间 × 目标时长 → 秒级期望落点 |

`--library` 可放在主命令或子命令之后，默认 `templates/`。

## 退出码（三个脚本一致）

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功（annotate 的警示项不算失败） |
| 2 | 输入文件不存在 / 模板不存在 |
| 3 | 校验失败或格式错误（stderr 给中文原因；annotate 不产出半成品卡片） |

## 测试与评测

```bash
python3 -m unittest discover tests      # 44 项单元测试
```

完整评测流程与证据见 [evals/README.md](../evals/README.md)；脚本层全程离线，
同输入重复运行输出一致（sha256 可复核）。
