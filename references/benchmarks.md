# 对标与参考逻辑（2026-11-02 二轮调研，覆盖 2026-09-19 首轮）

本文件回答三个问题：同类工具怎么做「拆爆款」、哪些规范/研究能给本仓库的阈值和口径
提供依据、本仓库与它们的差距在哪。每条结论附来源与检索日期（全部检索于 2026-11-02，
首轮条目注明 2026-09-19）。引用版权归原作者所有，仅作对比说明。

## 1. 对标清单

### 1.1 商业产品

| 产品 | 怎么拆 | 指标口径 / 输出 | 对本项目的启示 | 来源 |
| --- | --- | --- | --- | --- |
| 蝉妈妈「AI拆视频」 | 粘贴爆款链接 → AI 从文案、分镜、脚本、画面多维拆解；详情页有「拉分镜 / 提文案 / 爆点拆解 / 仿写」入口 | 运营圈文章给的口径：开场 3–5 秒抛悬念/痛点/利益点；统计文案时长与信息点分布间隔（节奏/信息密度）；收尾指令设计 | 「节奏/信息密度」是公认拆解维度，本项目 v0.2.0 完全没有；可在转写稿层面确定性给出段语速 | [chanmama.com/yunyingquan/question/4478](https://www.chanmama.com/yunyingquan/question/4478.html)、[article/1498](https://www.chanmama.com/yunyingquan/article/1498.html)、[ai.chanmama.com](https://ai.chanmama.com)（年费 ¥1,398 为首轮用户提供的实测数据） |
| 飞瓜数据 | 数据层：榜单、素材监测、直播分析 | 不输出可复用的结构模板 | 数据层不是本项目职责（首轮结论不变） | [feigua.cn](https://www.feigua.cn)（首轮 2026-09-19） |
| YouTube Studio「留存关键时刻」 | 平台用真实留存曲线标出 Intro / Spikes / Dips | Intro = 前 30 秒后仍在看的观众比例；需视频 ≥ 60 秒且 ≥ 100 次观看才显示；「typical retention」与最近 10 条同长度视频比较 | 开头是按**绝对秒数**度量的，不按全片占比；本项目把钩子按占比缩放到长视频是口径错误 | [support.google.com/youtube/answer/9314415](https://support.google.com/youtube/answer/9314415?hl=en) |
| TikTok 官方创意最佳实践 | 广告创意指南 | 「前 3 秒亮出内容主张」「钩子优先放在前 6 秒」「有钩子、讲卖点、以清晰 CTA 收尾」；文字每秒 5–10 词 | 给「钩子窗口 3–6 秒」一个官方出处；也说明钩子应以绝对秒计 | [ads.tiktok.com/help/article/creative-best-practices](https://ads.tiktok.com/help/article/creative-best-practices?lang=en) |
| Retention Analyzer（Product Hunt） | 把 YouTube 留存曲线与逐字稿对齐，指出掉点处在说什么；无留存数据时只做「预测」并明确标注 | 突降 vs 缓降、重看点、未闭合悬念、节奏问题 | 「实测 vs 预测」分开标注的做法与本项目「不打分、如实披露」一致；本项目没有留存数据，不做掉点预测 | [producthunt.com/p/retention-analyzer](https://www.producthunt.com/p/retention-analyzer/retention-analyzer) |
| 拆解训练营 / 人工拉片表 | 人工逐句暂停填表 | ¥5,000/人（首轮用户提供）；一条 0.5–1 小时 | 本项目只自动化可确定的部分（切块、校验、统计），角色判断仍归人/Agent | 首轮 2026-09-19 |

### 1.2 开源实现（GitHub，2026-11-02 检索 `爆款 拆解`、`短视频 拆解` 等）

| 项目 | 做法 | 关键逻辑 | 与本项目的差异 |
| --- | --- | --- | --- |
| [JuneYaooo/social-account-doctor](https://github.com/JuneYaooo/social-account-doctor)（337★，作者本人） | 账号体检 + 爆款拆解 + 仿写初稿 | `references/product-video-framework.md` 的五种带货配方全部用**绝对秒数**写分镜（镜1 0–3s、镜2 3–8s…），推荐时长 15–60s | 同一作者的配方库本来就按绝对秒定钩子；本仓库 apply 按占比缩放钩子与之矛盾，v0.3.0 修正 |
| [rico3cats/Rico3cats-wow-video-analyzer](https://github.com/rico3cats/Rico3cats-wow-video-analyzer)（30★） | FFmpeg + StepFun ASR + 视觉模型，六维度报告 | 提示词要求「黄金 3 秒必须抓住注意力」「每 5–8 秒一个小高潮」，各维度给 0–100 分 | 依赖模型打分与流量预测；本项目坚持不打分，只给可复核的结构事实 |
| [aispin/iskill-viral-teardown](https://github.com/aispin/iskill-viral-teardown) | 下载 + 本地转写 + 拆解报告 + 跨天拆解库 | 「前 3–5 秒第一句原话 + 钩子类型」；「有 srt 就标时间点，每段时长占比」；「节奏（语速/停顿/转折位）」；无逐字稿时强制标注「非真实拆解」、禁止编造原句 | 维度最接近本项目；但占比、节奏由模型口述，没有确定性校验；本项目的时间轴校验与例句逐字核对是差异点 |
| [g305595965/viral-video-deconstructor](https://github.com/g305595965/viral-video-deconstructor) | 爆点摘要 → 黄金 3 秒 → 逐镜结构 → 原创改写 → 合规闸门 | 镜头表含「情绪强度 1–10、节奏 快/中/慢」；节奏公式「钩子(1–2 镜) → 展开 → 高潮/反转(N-1) → 行动召唤(N)」；Whisper 本地转写 | 偏生成与改写；本项目不代写。其 Whisper 转写链路说明用户手里的稿子大量来自 Whisper |
| [3dudu/tiktok-video-analyzer](https://github.com/3dudu/tiktok-video-analyzer) | Gemini 逐帧分析 + 「停病药信买」框架匹配 + 飞书入库 | 画面层 + 固定框架匹配 | 画面层不在本项目范围 |
| [Jeorrysyd/xhs-viral-decoder](https://github.com/Jeorrysyd/xhs-viral-decoder)（8★） | 6 个小红书子 Skill，产出飞书文档 | 图文笔记为主 | 平台与载体不同 |
| [peterk/srt_equalizer](https://github.com/peterk/srt_equalizer)（42★） | 把 Whisper 的长字幕条切成短条 | 「切开后的片段按文本长度**比例**分配时间，且不超出原字幕条时间槽」 | 给本项目「同一字幕条内多句按字数比例插值时间」提供了现成做法 |

首轮（2026-09-19）结论「GitHub 上没有转写稿 → 结构标注 → 模板库的确定性实现」在二轮检索后仍成立：
同类开源项目全部把拆解交给大模型口述，没有时间轴合法性校验、例句逐字核对、标注一致性度量。

### 1.3 规范、研究与数据源

| 资料 | 关键事实 | 用在本项目哪里 |
| --- | --- | --- |
| Netflix 简体中文字幕规范 | 每行 16 字、最多 2 行；成人节目阅读速度 ≤ 9 字/秒；**不用逗号和句号，用一个空格代替**；问句必须用问号 | ① 中文字幕标点稀疏是规范而非异常 → 不能只靠终止标点切句；② 例句核对要忽略标点；③ 无标点切块上限 32 字（16×2） [来源](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215986007-Chinese-Simplified-Timed-Text-Style-Guide) |
| Netflix 字幕时间轴规范 | 字幕间隔最少 2 帧；24fps 下 3–11 帧的间隔必须合并成 2 帧；**间隔要么 2 帧要么 ≥ 半秒**；最短 20 帧（5/6 秒） | 半秒以下的间隔在规范字幕里会被抹平，≥ 0.5s 才是有意义的停顿 → 停顿阈值 0.8s 改 0.5s [来源](https://partnerhelp.netflixstudios.com/hc/en-us/articles/360051554394-Timed-Text-Style-Guide-Subtitle-Timing-Guidelines) |
| W3C WebVTT 规范 | 文件以 `WEBVTT` 开头；时间戳**小时可省略**（mm:ss.ttt）；可带 cue 设置、NOTE/STYLE/REGION 块、`<c>`/`<v>`/时间戳行内标签 | v0.2.0 把 .vtt 当纯文本解析（时间码混进正文），v0.3.0 补 VTT 解析 [来源](https://www.w3.org/TR/webvtt1/) |
| OpenAI Whisper 实测（本仓库 2026-11-02 真实运行） | `whisper --model small --language zh` 对 90 秒普通话朗读输出 31 条字幕：**无任何标点、相邻字幕条首尾相接（间隔 0）**，每条 2–5 秒；VTT 时间戳省略小时位 | 停顿规则在 Whisper 稿上完全失效，只能靠字数/时长上限切块 → 新增 6 秒时长上限；统计见 [evals/runs_v2/real_whisper_stats.json](../evals/runs_v2/real_whisper_stats.json) |
| Pellegrino, Coupé & Marsico (2011), *Language* | 普通话朗读约 5.18 音节/秒（参与比较的语言中最慢） | 32 字 ≈ 6 秒，与 TikTok「钩子 6 秒」一致；段语速的阅读参照（不作阈值） [论文 doi:10.1353/lan.2011.0057](https://doi.org/10.1353/lan.2011.0057)（5.18 这一数值取自二手综述，原文未逐字核对） |
| Wan, Lai & Yu (2025), ROCLING：台湾华语停顿时长 | 长停顿去离群后均值 426 ms、中位约 370–380 ms；3×IQR 剔除 > 1,016 ms 的值 | 0.8s 阈值高于多数句间长停顿，会欠切；0.5s 更贴近 [来源](https://aclanthology.org/2025.rocling-main.14/) |
| Pevzner & Hearst (2002), *Computational Linguistics* | 提出 WindowDiff，修正 Pk 对近似命中过罚、对段长敏感的问题；NLTK 有实现，Pk 默认窗口 = 参照平均段长的一半 | 新增 agreement.py 的边界一致性口径 [论文](https://bebop.berkeley.edu/papers/pevzner-01.pdf)、[NLTK](https://www.nltk.org/api/nltk.metrics.segmentation.html) |
| Fournier & Inkpen (2012) 等对 WindowDiff 的批评 | WindowDiff 对两端误差欠罚；提出 Segmentation Similarity / 边界相似度 | 因此不只报 WindowDiff，同时报带容差的边界 P/R/F1 与逐块分歧 [来源](https://arxiv.org/abs/1204.2847) |
| Cohen (1960) kappa；Landis & Koch (1977) 分档 | 0.61–0.80「较强」、0.81–1「几乎完全一致」；该分档是作者经验约定，并非统计检验 | 角色一致度用 kappa，分档只作阅读参照并在报告里写明 [Wikipedia 汇总](https://en.wikipedia.org/wiki/Cohen%27s_kappa) |
| Save the Cat 节拍表 | 按全片百分比给**点值**（催化剂 ~10%、中点 50%、一无所有 75%），而非区间包络 | 模板落点改成「中位点 + 观测范围」，不再把 [最早起点, 最晚终点] 包络当落点 [来源](https://reedsy.com/blog/guide/story-structure/save-the-cat-beat-sheet/) |
| TraMineR（R 序列分析工具包，最优匹配距离） | 社会科学对状态序列做距离与聚类的标准工具 | 记录为未来方向：模板库 > 20 张卡后可按序列距离聚类自动分模板；当前样本太少，不做 [CRAN](https://cran.r-project.org/web/packages/TraMineR/) |

数据源现状（2026-11-02 实测）：本仓库不抓取任何平台。用户的稿子主要来自剪映导出 SRT、
飞书妙记、Whisper（SRT/VTT）。本次尝试用 yt-dlp 拉公开视频做真实样本：YouTube 要求登录
（「Sign in to confirm you're not a bot」），B 站搜索接口返回 HTTP 412，均未绕过；改用
Wikimedia Commons 上 CC BY-SA 4.0 的普通话有声条目做真实 ASR 输入。

## 2. 对比表：本项目 vs 对标

| 维度 | 蝉妈妈等商业平台 | 开源拆解 Skill（iskill 等） | 本项目 v0.2.0 | 本项目 v0.3.0 |
| --- | --- | --- | --- | --- |
| 输入 | 视频链接 | 链接 / 文件 / 转写稿 | SRT、纯文本 | SRT、**WebVTT**、纯文本 |
| 段角色判断 | 模型 | 模型 | Agent 判定 + 脚本校验 | 同左 |
| 时间轴校验 | 不公开 | 无 | 有（重叠/倒置/越界/对齐） | 同左 + 句块粒度 ≤ 6 秒 |
| 例句核对 | 无 | 无 | 逐字（去空白） | 逐字（去空白、标点、全半角） |
| 开头 / 钩子 | 「黄金 3 秒」口述 | 「前 3–5 秒」口述 | 只有占比 | 开场是否钩子、钩子止于第几秒，对照 TikTok 3/6 秒参照 |
| 节奏 | 信息点间隔、情绪曲线 | 模型口述语速/停顿 | 无 | 段语速（字/秒，确定性，不打分） |
| 模板落点 | 无 | 填空模板 | min–max 包络 × 时长 | 中位点 + 观测范围；钩子按绝对秒封顶；外推/冷启动提示 |
| 标注一致性 | 无 | 无 | 只声明「边界主观」 | agreement.py：kappa、边界 F1、WindowDiff |
| 打分 / 流量预测 | 有 | 部分有（0–100 分） | 不做 | 不做 |

## 3. 可借鉴、已采纳的逻辑

1. **钩子按绝对秒计**（YouTube Intro 30 秒、TikTok 3/6 秒、作者本人配方库 0–3s）→ apply 钩子终点取 min(样本绝对秒中位, 占比换算)。
2. **中文字幕标点稀疏是常态**（Netflix 规范、Whisper 实测）→ 按字幕条带标点的比例选择切法；例句核对忽略标点。
3. **字幕间隔 ≥ 0.5 秒才是有意义的停顿**（Netflix）→ 停顿阈值 0.8s → 0.5s。
4. **句块粒度要细于钩子窗口**（TikTok 6 秒；16 字×2 行 ≈ 32 字 ≈ 6 秒）→ 无标点切块上限 60 字 → 32 字并加 6 秒上限。
5. **多句同条按文本长度比例分时**（srt_equalizer）→ 修复 0 时长句块。
6. **节拍表给点值不给包络**（Save the Cat）→ 中位数落点 + 观测范围。
7. **分割一致性用 WindowDiff + 边界 F1 + kappa**（Pevzner & Hearst；Fournier；Landis & Koch）→ 新增 agreement.py。
8. **节奏是公认维度**（蝉妈妈、iskill、deconstructor）→ 段语速作为描述值。

## 4. 仍存在的差距（如实列出）

- **没有留存数据**：YouTube Studio / Retention Analyzer 能把结构和掉点对上，本项目只看转写稿，
  无法验证「这个结构为什么留得住人」。这是边界，不在 v0.3.0 范围。
- **没有画面层**：分镜、景别、字幕特效（蝉妈妈、rico3cats、3dudu 都做）不覆盖。
- **模板样本仍是合成冷启动**：5 个模板的位置区间由 1–2 张合成卡支撑，没有真实爆款统计。
- **真实爆款稿未入库**：YouTube/B 站在本环境需要登录或被风控，真实样本只用了 CC 授权的
  维基有声条目（朗读体，不是口播爆款），只能验证解析层，不能验证结构判断。
- **序列聚类未做**：模板仍按「完全相同的段序列」聚合，带循环的卡不参与位置统计。
