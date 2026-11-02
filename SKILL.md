---
name: viral-structure-teardown
description: 把爆款视频/口播的转写稿（SRT、WebVTT 或纯文本）按钩子、留人、转折、转化四段式做结构标注（Agent 判定段落、脚本做时间轴与对齐校验、可量化两次标注的一致性），多条拆解蒸馏成可复用的结构模板库，写新脚本时按中位数给出秒级期望落点；只做结构标注与模板沉淀，不打分、不代写、不抄袭，全程本地运行。
---

# 爆款结构拆解

当用户要「拆解这条爆款的结构」「这条视频的钩子转折在哪」「帮我沉淀能套用的脚本模板」
时使用本 Skill。交付物是拆解卡（结构时间轴 + 例句 + 开场钩子与语速描述 + 结构总评）和
可套用的结构模板，不是内容质量评分，也不是代写文案。

## 工作边界

- 只处理用户自备的转写稿（SRT / WebVTT / 纯文本），全部本地解析与比对，不需要任何平台授权，
  不替用户抓取平台视频。
- 段边界是主观判定：同一稿子两次标注的转折点可能不同。占比存中位数与观测范围，落点仅供参考，
  必须向用户声明边界主观，不得把标注说成客观事实。需要量化时用一致性脚本（见流程第 4 步）。
- 四段不齐时如实标注：纯干货清单可能没有转折，缺哪段就写「未检出」，禁止硬凑四段。
- 开场钩子（3/6 秒）与段语速只是描述和参照，不得说成「合格/不合格」，也不得据此打分。
- 红线：不打分（不做内容质量评分、不预测流量）；不代写（不生成、不改写文案）；
  不抄袭（例句只用于佐证结构功能，套用模板时必须替换为用户的原创内容）。
- 无时间码的纯文本无法做时间轴标注：请用户提供 SRT/VTT 或补齐时间戳，不要虚构时间。

## 默认流程

1. **解析转写稿**：`python3 scripts/parse_transcript.py 转写稿.srt -o blocks.json`（.vtt 同样可用）。
   标点充足时按终止标点切句（同一字幕条内多句按字数比例分时）；标点稀疏或无标点
   （Whisper、剪映、Netflix 规范的中文字幕都很常见）时在字幕条边界切：停顿 ≥ 0.5 秒、
   上一条以终止标点结尾、或并入后超过 32 字 / 6 秒就切开，保证钩子能落在句块边界上。
   摘要行里出现「字幕条时间重叠」等提示时，转告用户复核来源字幕。参数见 [docs/usage.md](docs/usage.md)。
2. **归类结构段**：读句块 JSON，把每段判入 hook（钩子）/ build（留人）/ twist（转折）/
   cta（转化），手法口径见 [references/structure-schema.md](references/structure-schema.md)。
   逐段记录 start/end（必须贴合句块边界）、evidence（从该时间段内摘一句原文）、
   reason（命中哪种手法），并撰写 structure_note（结构总评）。
3. **校验并渲染拆解卡**：`python3 scripts/annotate.py blocks.json annotation.json -o 拆解卡.md --json 拆解卡.json`。
   时间轴非法（重叠/倒置/越界）→ exit 3，必须修标注；覆盖率、四段齐缺、边界对齐、
   例句命中（忽略标点与全半角）都会列出。卡上的「开场钩子」行与「语速」列是描述值：
   向用户解释时说「钩子止于第 X 秒，平台建议是 3 秒亮主张、6 秒内完成钩子」，不要说「不合格」。
4. **（可选）量化边界主观性**：用户质疑边界、或同一稿子有两份标注（Agent 两次、或 Agent 与人工）时，
   `python3 scripts/agreement.py blocks.json 标注A.json 标注B.json -o 一致性.md`，
   报告角色一致率、Cohen kappa、边界 F1（±1 句块）、WindowDiff 与分歧句块。
   一致性低就把分歧句块交给用户决定，不要替用户选一份当「正确答案」。
5. **蒸馏模板**：多条同类拆解后
   `python3 scripts/templates.py distill 卡1.json 卡2.json --template-id <id> --name <名> --genres <题材>`
   聚合出模板（段序列 + 每段起止的中位数与观测范围 + 句式模式 + 例句），落库 `templates/`；
   `list` / `show` 检索。入库前把模板给用户确认。
6. **套用落点**：`python3 scripts/templates.py apply <template_id> --duration <秒数>`。
   落点取支撑卡的中位数，首段钩子终点取「样本绝对秒」与「占比换算」的较小者
   （长视频不把钩子按比例拉长）。输出里的 ⚠ 外推、⚠ 冷启动提示必须原样告诉用户。
   按落点给逐段提纲时，例句只示范功能，提纲必须用用户的原创内容填充。

## 支持文件

- [references/structure-schema.md](references/structure-schema.md)：四段式口径、句块/标注/模板 JSON schema 与示例。
- [references/benchmarks.md](references/benchmarks.md)：对标产品、开源实现与规范研究，各阈值的出处。
- [docs/usage.md](docs/usage.md)：四个脚本的参数、退出码与评测复现说明。
- [evals/README.md](evals/README.md)：评测证据入口。
