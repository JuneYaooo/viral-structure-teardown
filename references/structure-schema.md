# 结构框架与模板 schema

四段式（钩子/留人/转折/转化）描述的是口播稿的时间顺序，与 SRT 时间戳天然同构：
一条转写稿解析成句块后，标注就是把连续句块归入段角色序列。本文件给出角色口径与
三个 JSON 的字段定义。

## 段角色口径

| 角色 | 中文 | 功能 | 常见手法 | 可选 intent 标签 |
| --- | --- | --- | --- | --- |
| hook | 钩子 | 前 3–7 秒留人 | 悬念、反常识、痛点提问、强冲突、利益受损开局、二次钩子（可复现） | AIDA-Attention |
| build | 留人 | 铺垫与展开，堆可信度 | 立标准/清单逐条、过程叙事、交锋升级 | AIDA-Interest/Desire |
| twist | 转折 | 制造记忆点的反转 | 反常识结论、实锤证据、剧情反转 | HSO-Story |
| cta | 转化 | 关注/引流/资料引导 | 评论区资料、下期预告、点关注 | HSO-Offer |

要点：

- 段角色是**序列不是四槽**：允许缺段（如无转折的清单体），允许复现（如双钩子循环
  钩子→留人→转折→钩子→留人→转化）。
- 二次钩子是重新拉注意力的话术转折，标回 hook 而不是 twist：它不产生新信息，
  只制造「还没完」的期待。
- 标注段边界必须贴合句块边界；段边界主观，占比存区间不存点值。

## blocks.json（parse_transcript.py 产出）

```json
{
  "version": "0.2.0",
  "source": "evals/fixtures/standard_four_part_v1.srt",
  "format": "srt",
  "timed": true,
  "duration_s": 58.0,
  "punctuation": true,
  "strategy": "sentence_punct",
  "block_count": 11,
  "blocks": [
    {"i": 0, "start": 0.0, "end": 4.0, "text": "别再跟风买网红锅了，我自费五千块，把全平台销量前五全测了一遍。"}
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| timed | SRT 为 true；纯文本为 false（start/end 为 null，无法做时间轴标注） |
| strategy | sentence_punct（按句）/ pause_gap（无标点按 >0.8s 停顿）/ fixed_length（纯文本 40 字） |
| blocks[].start / end | 秒，保留两位；取所在字幕条区间 |

## annotation.json（Agent 产出，annotate.py 消费）

```json
{
  "video_id": "standard-four-part-v1",
  "title": "网红锅五款横评（合成样本）",
  "genre": "好物测评",
  "transcript": "evals/fixtures/standard_four_part_v1.srt",
  "structure_note": "整体套路的一段话总评（Agent 撰写位）",
  "patterns": {"hook": ["别再…了，我自费…"], "twist": ["最贵的…反而垫底"]},
  "segments": [
    {"role": "hook", "start": 0.0, "end": 7.0,
     "evidence": "别再跟风买网红锅了", "reason": "否定式开场+自费背书，强冲突钩子"}
  ]
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| segments[].role | 是 | hook / build / twist / cta，按时间顺序排列 |
| segments[].start / end | 是 | 秒；end > start、无重叠、单调、不超全片时长，且贴合句块边界 |
| segments[].evidence | 建议 | 该时间段内的一句原文；脚本逐字核对（去空白归一） |
| segments[].reason | 建议 | 命中的手法，供拆解卡「归类理由」列与人工复核 |
| patterns | 否 | 该稿的句式模式（填空模板），蒸馏时并入模板 |

脚本确定性校验：时间轴合法性、覆盖率与未覆盖区间、四段齐缺（缺段如实标注）、
边界对齐（切开句块处列出）、例句命中。校验失败 exit 3，不产出半成品卡片。

## 模板 JSON（templates.py distill 产出）

```json
{
  "version": "0.2.0",
  "template_id": "twist-fourpart-v1",
  "name": "标准四段反转体",
  "created": "2026-09-19",
  "source_cards": ["standard-four-part-v1", "double-hook-loop-v1"],
  "card_count": 2,
  "genres": ["好物测评", "剧情维权"],
  "duration_range_s": [58.0, 63.0],
  "role_sequences": [
    {"sequence": ["hook", "build", "twist", "cta"], "count": 1},
    {"sequence": ["hook", "build", "twist", "hook", "build", "cta"], "count": 1}
  ],
  "primary_sequence": ["hook", "build", "twist", "cta"],
  "positions": [
    {"position": 1, "role": "hook", "ratio": [0.0, 0.1207], "sample_cards": 1,
     "functions": ["否定式开场"], "example_lines": ["别再跟风买网红锅了"],
     "patterns": ["别再…了，我自费…全测了一遍"]}
  ],
  "role_ratio_ranges": {"hook": [0.0, 0.4841]},
  "intent_map": {"hook": "AIDA-Attention", "build": "AIDA-Interest/Desire",
                  "twist": "HSO-Story", "cta": "HSO-Offer"},
  "red_lines": ["只沉淀结构位置与句式功能，不收录整段文案，不做内容代写",
                 "不打分：不做流量预测与内容质量打分",
                 "例句仅示范该段功能，套用时必须替换为原创内容"]
}
```

| 字段 | 说明 |
| --- | --- |
| role_sequences | 观测到的全部段序列及次数；主序列取最常见（并列取更短者） |
| positions[].ratio | 该序位在各卡中的占比区间 [min_start, max_end]，即观测包络（样本增加时只增不减）；只统计与主序列一致的卡 |
| positions[].sample_cards | 支撑该序位的卡片数（样本量必须如实随产物披露，模板说明的段位表含「支撑卡数」列） |
| role_ratio_ranges | 每个角色跨全部卡的总出现区间（含复现段，供参考） |

apply 落点：期望区间（秒）= positions[].ratio × 目标时长，节拍表式按百分比打点；
落点只约束结构位置与时长占比，不约束内容本身。

## 与其他框架的映射（可选标签，不单独成体系）

- AIDA（注意/兴趣/欲望/行动）：hook≈Attention，build≈Interest/Desire，cta≈Action。
- Hook-Story-Offer：hook 对应 Hook，twist/build 叙事对应 Story，cta 对应 Offer。
- Save the Cat 节拍表：占比区间 → 期望落点的换算思路与此同源，适用于时长打点。
