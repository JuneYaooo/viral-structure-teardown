# 迭代记录：从失败到修复

以下为本仓库开发与复审过程中真实发生并修复的缺陷，每条附发现场景与回归方式。
迭代 1–3 发生在 v0.1.0 开发期，迭代 4–5 发生在 v0.2.0 复审期。

## 迭代 1（开发期）：templates.py 的 --library 放在子命令后直接报错

- 过程：首轮冒烟按最自然的写法 `templates.py distill card.json … --library /tmp/lib`
  调用，argparse 报 `unrecognized arguments: --library /tmp/lib`——`--library` 只定义在
  主解析器上，子命令后不可用。
- 归因：argparse 主解析器选项必须位于子命令之前，与用户直觉相反。
- 修复：把 `--library` 以 `parents=[lib_opt]` 挂到全部四个子命令，并用
  `default=argparse.SUPPRESS` 避免覆盖全局默认值；两种位置现在均可。

## 迭代 2（开发期）：非法段夹中间时，重叠漏检

- 过程：用坏时间轴夹具（bad_timeline_annotation_v1.json）做拦截测试，首轮只报出
  2 类错误（end≤start、越界）——设计上应有三类。排查发现第 3 段与前段的「重叠」
  错误没报：它前面的第 2 段本身非法（end≤start），`prev_end` 被重置为 None，
  重叠检查被跳过；更早的合法段不再参与比较。
- 归因：重叠校验只看「紧邻上一段」，非法段会打断比较链。
- 修复：新增 `last_valid_end`（最近一个完全合法段的 end，穿透非法段持续比较），
  且只在该段自身无错误时更新，避免把非法段的越界时间当基准；新增单测
  `test_overlap_across_invalid_middle_segment`，并重设计坏夹具让三类错误各自独立
  可见（现在 bad_timeline_rejected.txt 里三条错误齐备）。

## 迭代 3（测试期）：无时间码输入在函数层不设防 + 两处测试期望错误

- 过程：补 `build_card` 单测时发现直接调用该函数（绕过 CLI 的 run()）不会拒绝
  无时间码句块；同批 44 项测试另有 3 项失败，逐一核查：2 项是测试自身写错
  （覆盖率期望误写为 100%，实际标注只覆盖 0–12s 应为 20.7%；确定性对比误把
  source 路径纳入比较），1 项是模板红线文案缺「不打分」字样导致断言失败。
- 修复：`build_card` 前置 ValidationError（与 CLI 行为一致，双保险）；覆盖率期望
  改为按标注时长精确计算；确定性对比排除 source 字段；红线文案改为
  「不打分：不做流量预测与内容质量打分」。修复后 44/44 通过。

## 迭代 4（v0.2.0 复审期）：评测记录数字勘误 + 支撑卡数披露

- 过程：独立复审逐条核对评测记录与随卷产物，发现 c5 的 case 描述与 judgment 理由
  写的是「95 字 → 3 块（40/40/15）」，但随卷产物 blocks_no_punct_v1.json 显示夹具
  自 v0.1.0 起就是 118 字、切块 40/40/38——核心结论（3 块、fixed_length、timed=false）
  不受影响，但数字与产物不符。
- 修复：cases_v1.jsonl 与 judgments_v1.jsonl 按产物勘误为「118 字 → 3 块（40/40/38）」，
  judgment 理由注明勘误来源；复算 summary_v1.json 与原文件逐字节一致（评分未变）。
- 同批修复：模板 Markdown 段位表新增「支撑卡数」列（此前 positions[].sample_cards
  只存在于 JSON，人工看模板说明时看不到每个序位的样本量）；agents/openai.yaml
  引用的 ./assets/icon.svg 此前不存在，已补上图标文件。

## 迭代 5（v0.2.0）：模板库扩充与包络语义澄清

- 过程：为缓解「冷启动期位置区间仅 1 张卡支撑」，新写 3 条原创合成转写稿
  （知识口播钩子前置平铺型 62s、带货双转折型 75s、剧情无转化软种草型 70s），
  各走 parse → 标注 → annotate 校验（边界 0 错位、例句全命中、缺段如实标注）
  → distill 入库；其中 knowledge_flat_v1 与既有 no_twist_listicle_v1 同主序列，
  共同蒸馏出 flat-notwist-v1，位置区间首次获得 2 张卡支撑。模板库 2 → 5 个。
- 聚合逻辑审查结论：占比区间取各支撑卡的 min–max 观测包络，样本从 2 增到 5 时
  区间只会外扩不会收窄（新增测试 EnvelopeStabilityTests 固化该语义：包络单调不减、
  sample_cards 随匹配卡数增长、蒸馏确定性、apply 披露样本量）。据此勘误文档中
  「随拆解扩充收窄」的说法——扩样本带来的是「区间覆盖真实波动 + 样本量披露增强」，
  不是区间变窄；若要收窄需对区间取分位数或截尾，属未来可选增强，当前不做
  （样本 2→5 时分位数本身不稳定）。
- 复利演示：5 模板库对新选题（90 秒无转折知识口播）apply flat-notwist-v1，
  落点注明「位置区间样本 2 张拆解卡」（v0.1.0 时为 1 张），产物见
  runs_v1/apply_flat_notwist_90s.md 与 runs_v1/library_list_v0.2.0.txt。

## 已知限制（截至 v0.2.0）

- 模板库共 5 个模板，均为冷启动期：twist-fourpart-v1 的位置区间由 1 张卡支撑
  （其余卡段序列不同，只进入 role_ratio_ranges），flat-notwist-v1 由 2 张卡支撑，
  其余 3 个模板各 1 张卡；每个序位的支撑卡数已在模板说明与 apply 产物中逐项注明。
- listicle-notwist-v1 仅 1 张 48s 卡，参考时长区间无跨度，不承诺外推到其他时长
  （同序列的 flat-notwist-v1 覆盖 48–62s，可作跨时长参考）。
- 无标点 SRT 的停顿切分（gap>0.8s）按固定阈值，语速快的口播可能欠切，需人工复核。
- 占比区间为 min–max 包络，样本增加时只增不减；对离群卡敏感，样本量大后可考虑
  分位数聚合（未实现）。
- 判定为开发 Agent 自评（model_only），尚未独立人工复核。
