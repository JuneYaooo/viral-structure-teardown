# 迭代记录：从失败到修复

以下均为本仓库 v0.1.0 开发过程中真实发生并修复的缺陷，每条附发现场景与回归方式。

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

## 已知限制（未在本次修复）

- 模板库冷启动：twist-fourpart-v1 的位置区间目前只有 1 张卡支撑（另一张卡段序列
  不同，只进入 role_ratio_ranges），apply 落点标注了样本量；随模板库扩充收窄。
- listicle-notwist-v1 仅 1 张 48s 卡，参考时长区间无跨度，不承诺外推到其他时长。
- 无标点 SRT 的停顿切分（gap>0.8s）按固定阈值，语速快的口播可能欠切，需人工复核。
- 判定为开发 Agent 自评（model_only），尚未独立人工复核。
