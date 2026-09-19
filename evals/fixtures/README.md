# 夹具说明（fixtures）

本目录所有文件均为**人工编写的合成样本（synthetic fixtures）**：
转写稿文案、账号情境、金额、题材全部为本仓库原创虚构，不对应任何真实视频、
真实账号或真实文案；标注与模板也只覆盖结构层，不收录整段可传播文案。

| 文件 | 用途 |
| --- | --- |
| standard_four_part_v1.srt | 标准四段结构（钩子→留人→转折→转化），58s 好物测评口播 |
| no_twist_listicle_v1.srt | 缺转折结构（钩子→留人→留人→转化），48s 干货清单口播 |
| double_hook_loop_v1.srt | 双钩子循环结构（钩子→留人→转折→钩子→留人→转化），63s 剧情维权口播 |
| no_punctuation_v1.txt | 全篇无标点纯文本（118 字），测按长度切块路径 |
| knowledge_flat_v1.srt | 钩子前置平铺型（钩子→留人→留人→转化），62s 知识口播（v0.2.0 新增） |
| double_twist_v1.srt | 双转折型（钩子→留人→转折→留人→转折→转化），75s 带货测评口播（v0.2.0 新增） |
| soft_seed_v1.srt | 无转化软种草型（钩子→留人→转折→留人），70s 剧情号（v0.2.0 新增） |
| standard_four_part_annotation_v1.json | 标准四段的 Agent 标注（段边界贴合句块边界） |
| no_twist_listicle_annotation_v1.json | 缺转折标注（转折如实标缺） |
| double_hook_loop_annotation_v1.json | 双钩子循环标注（hook 复现两次） |
| bad_timeline_annotation_v1.json | 非法时间轴标注（end≤start、重叠乱序、越界），测校验拦截 |
| misplaced_evidence_annotation_v1.json | 时间轴合法但例句错位的标注，测例句核对（回归用） |
| knowledge_flat_annotation_v1.json | 钩子前置平铺标注（无转折，如实标缺） |
| double_twist_annotation_v1.json | 双转折标注（twist 复现两次） |
| soft_seed_annotation_v1.json | 软种草标注（无转化段，cta 如实标缺） |

五条 SRT 的段位设计（供评测核对「标注是否落在设计位置」）：

| 夹具 | 设计段位（秒） | 设计段序列 |
| --- | --- | --- |
| standard_four_part_v1 | hook 0–7 ｜ build 7–33 ｜ twist 33–45 ｜ cta 45–58 | 钩子→留人→转折→转化 |
| no_twist_listicle_v1 | hook 0–7 ｜ build 7–19 ｜ build 19–36 ｜ cta 36–48 | 钩子→留人→留人→转化（无转折） |
| double_hook_loop_v1 | hook 0–7.5 ｜ build 7.5–20 ｜ twist 20–26.5 ｜ hook 26.5–30.5 ｜ build 30.5–50 ｜ cta 50–63 | 钩子→留人→转折→钩子→留人→转化 |
| knowledge_flat_v1 | hook 0–6 ｜ build 6–26 ｜ build 26–46 ｜ cta 46–62 | 钩子→留人→留人→转化（无转折，钩子前置） |
| double_twist_v1 | hook 0–7 ｜ build 7–22 ｜ twist 22–34 ｜ build 34–50 ｜ twist 50–63 ｜ cta 63–75 | 钩子→留人→转折→留人→转折→转化 |
| soft_seed_v1 | hook 0–7 ｜ build 7–26 ｜ twist 26–38 ｜ build 38–70 | 钩子→留人→转折→留人（无转化，软种草） |

v0.2.0 新增的三条夹具为模板库扩充样本：knowledge_flat_v1 与 no_twist_listicle_v1 同主序列，
二者共同支撑 flat-notwist-v1（无转折平铺讲解体）的位置区间；double_twist_v1、soft_seed_v1
各自支撑一个新模板。
