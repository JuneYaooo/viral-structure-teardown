---
name: viral-structure-teardown
description: 把爆款视频/口播的转写稿按钩子、留人、转折、转化四段式做结构标注（Agent 判定段落、脚本做时间轴与对齐校验），多条拆解蒸馏成可复用的结构模板库，写新脚本时按占比给出秒级期望落点；只做结构标注与模板沉淀，不打分、不代写、不抄袭，全程本地运行。
---

# 爆款结构拆解

当用户要「拆解这条爆款的结构」「这条视频的钩子转折在哪」「帮我沉淀能套用的脚本模板」
时使用本 Skill。交付物是拆解卡（结构时间轴 + 例句 + 结构总评）和可套用的结构模板，
不是内容质量评分，也不是代写文案。

## 工作边界

- 只处理用户自备的转写稿（SRT 或纯文本），全部本地解析与比对，不需要任何平台授权。
- 段边界是主观判定：同一稿子两次标注的转折点可能不同。占比只存区间，落点仅供参考，
  必须向用户声明边界主观，不得把标注说成客观事实。
- 四段不齐时如实标注：纯干货清单可能没有转折，缺哪段就写「未检出」，禁止硬凑四段。
- 红线：不打分（不做内容质量评分、不预测流量）；不代写（不生成、不改写文案）；
  不抄袭（例句只用于佐证结构功能，套用模板时必须替换为用户的原创内容）。
- 无时间码的纯文本无法做时间轴标注：请用户提供 SRT 或补齐时间戳，不要虚构时间。

## 默认流程

1. **解析转写稿**：`python3 scripts/parse_transcript.py 转写稿.srt -o blocks.json`。
   SRT 按句切块（终止标点：。！？!?；;…），ASR 无标点时按 >0.8s 停顿切块，纯文本
   无标点按 40 字定长切块。参数与失败行为见 [docs/usage.md](docs/usage.md)。
2. **归类结构段**：读句块 JSON，把每段判入 hook（钩子）/ build（留人）/ twist（转折）/
   cta（转化），手法口径（悬念/反常识/痛点提问/强冲突等）见
   [references/structure-schema.md](references/structure-schema.md)。逐段记录 start/end
   （必须贴合句块边界）、evidence（从该时间段内摘一句原文）、reason（命中哪种手法），
   并撰写 structure_note（结构总评）。
3. **校验并渲染拆解卡**：`python3 scripts/annotate.py blocks.json annotation.json -o 拆解卡.md --json 拆解卡.json`。
   脚本确定性校验时间轴（重叠/倒置/越界 → exit 3 必须修标注）、覆盖率、四段齐缺、
   边界对齐与例句命中；校验通过才渲染拆解卡。解释这条爆款的套路时以 structure_note
   和各角色占比为依据，不给内容打分。
4. **蒸馏模板**：多条同类拆解后
   `python3 scripts/templates.py distill 卡1.json 卡2.json --template-id <id> --name <名> --genres <题材>`
   聚合出模板（段序列模式 + 每段占比区间 + 句式模式 + 例句），落库 `templates/`；
   `list` / `show` 检索。入库前把模板给用户确认。
5. **套用落点**：写新脚本时
   `python3 scripts/templates.py apply <template_id> --duration <秒数>`
   把占比区间换算成秒级期望落点（节拍表式打点），按落点给逐段提纲；例句仅示范功能，
   提纲必须用用户的原创内容填充。

## 支持文件

- [references/structure-schema.md](references/structure-schema.md)：四段式口径、句块/标注/
  模板三个 JSON schema 与示例。
- [references/benchmarks.md](references/benchmarks.md)：与蝉妈妈/飞瓜/训练营及开源生成器的定位对比。
- [docs/usage.md](docs/usage.md)：三个脚本的参数、退出码与评测复现说明。
- [evals/README.md](evals/README.md)：评测证据入口。
