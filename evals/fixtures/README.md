# 夹具说明（fixtures）

本目录所有文件均为**人工编写的合成样本（synthetic fixtures）**：
转写稿文案、账号情境、金额、题材全部为本仓库原创虚构，不对应任何真实视频、
真实账号或真实文案；标注与模板也只覆盖结构层，不收录整段可传播文案。

| 文件 | 用途 |
| --- | --- |
| standard_four_part_v1.srt | 标准四段结构（钩子→留人→转折→转化），58s 好物测评口播 |
| no_twist_listicle_v1.srt | 缺转折结构（钩子→留人→留人→转化），48s 干货清单口播 |
| double_hook_loop_v1.srt | 双钩子循环结构（钩子→留人→转折→钩子→留人→转化），63s 剧情维权口播 |
| no_punctuation_v1.txt | 全篇无标点纯文本，测按长度切块路径 |
| standard_four_part_annotation_v1.json | 标准四段的 Agent 标注（段边界贴合句块边界） |
| no_twist_listicle_annotation_v1.json | 缺转折标注（转折如实标缺） |
| double_hook_loop_annotation_v1.json | 双钩子循环标注（hook 复现两次） |
| bad_timeline_annotation_v1.json | 非法时间轴标注（end≤start、重叠乱序、越界），测校验拦截 |
| misplaced_evidence_annotation_v1.json | 时间轴合法但例句错位的标注，测例句核对（回归用） |

三条 SRT 的段位设计（供评测核对「标注是否落在设计位置」）：

| 夹具 | 设计段位（秒） | 设计段序列 |
| --- | --- | --- |
| standard_four_part_v1 | hook 0–7 ｜ build 7–33 ｜ twist 33–45 ｜ cta 45–58 | 钩子→留人→转折→转化 |
| no_twist_listicle_v1 | hook 0–7 ｜ build 7–19 ｜ build 19–36 ｜ cta 36–48 | 钩子→留人→留人→转化（无转折） |
| double_hook_loop_v1 | hook 0–7.5 ｜ build 7.5–20 ｜ twist 20–26.5 ｜ hook 26.5–30.5 ｜ build 30.5–50 ｜ cta 50–63 | 钩子→留人→转折→钩子→留人→转化 |
