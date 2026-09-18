# 评测（Evals V1）

本目录保存 viral-structure-teardown 的行为证据：题集、量表、运行协议、真实产物与逐题判断。

## 评测分层

1. **脚本行为层**：对 `evals/fixtures/` 的合成夹具运行三个脚本（命令见
   [docs/usage.md](../docs/usage.md)），逐条核对 [cases_v1.jsonl](cases_v1.jsonl) 的
   required/forbidden 原子检查。脚本为确定性比对，case c6 显式验证同一标注两次渲染
   sha256 一致，case c4 验证非法时间轴被 exit 3 拦截且不产出半成品。
2. **Agent 工作流层**：开发 Agent 读句块 JSON 后按设计段位标注三份转写稿并提取例句，
   经 annotate.py 校验落位，按 [rubric_v1.md](rubric_v1.md) 五维度判定。
   每条夹具的设计段位公开在 [fixtures/README.md](fixtures/README.md)，
   「标注是否落在设计位置」可逐段机械核对。

## 当前状态（2026-09-19，v0.1.0）

- **9/9 用例通过，0 硬失败**；逐题判断见 [judgments_v1.jsonl](judgments_v1.jsonl)，
  汇总见 [summary_v1.json](summary_v1.json)（由 [scripts/aggregate_results.py](scripts/aggregate_results.py)
  从逐题判断复算）。
- 三轮真实缺陷与修复见 [iteration_notes.md](iteration_notes.md)：CLI 参数位置、
  非法段夹中间时的重叠漏检、无时间码输入在函数层不设防；单元测试 44/44 通过。
- 夹具全部为合成样本（见 [fixtures/README.md](fixtures/README.md)），转写稿文案全部
  原创，不对应任何真实视频。
- **诚实披露**：判定为开发 Agent 自评（model_only），尚未独立人工复核；模板库冷启动
  位置区间仅 1 张卡支撑，apply 落点样本量已在产物中注明。

## 复现

命令与参数见 [docs/usage.md](../docs/usage.md)；脚本层全程离线，无需任何 API 密钥。
