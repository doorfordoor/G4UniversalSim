# 阶段 0 交付与待审清单（DeepSeek → Astra）

- 日期：2026-10-28
- 分支/提交：`roadmap/F6-live-progress` / `02c0dc6`（`codex` 已快进并推送同一提交）
- 状态简报：[ASTRA-BRIEF.md](../ASTRA-BRIEF.md)（先读它，再看历史审计）
- 证据：`docs/verification/stage0-20261027/`（76 PASS / 0 FAIL / 0 SKIP 报告、逐用例日志、
  F6 成对性能采样、exe SHA-256、复现命令、不证明清单）

## 已完成的修复

B1 `[scoring.displacement]` 粒子名两阶段校验；B2 主 INI 重复声明可见化（`config_duplicate_count`）；
B3 敏感探测器按配置名创建 + `enableSD/setSDName` PreInit 门禁；B4 `setSeed` PreInit 门禁；
GUI 源几何不再被 Setup 栏静默重置；F6 终态文案、日志视图上限与跨 chunk 行缓冲。

## 请你审的（按优先级）

1. **命令族状态门禁权威分类表**：哪些 Messenger 命令族“改了缓存、内核没变、进程仍退出 0”。
   建议直接读 `src/*/*Messenger.cc` 与 `main.cc` 的注册点，输出表格：命令族 → 现有门禁 →
   晚调用实际后果 → 建议。已知 Detector/Material/Source 三族历史上缺门禁。
2. B1 两阶段校验是否有漏网（worker 克隆、空表、重复规范名、`[scoring.displacement]` 之外的 DDD 入口）。
3. B3 默认名 `AIHLParticleSD` 被配置改掉后，输出文件/敏感体名/touchable 路径是否跟随；有无下游按名字硬编码。
4. B4 之外还有没有初始化后改种子的路径（CLI 覆盖、macro、`context_.SetSeed`、`/random/*`），
   `configured_seed` 是否仍可能与内核实际种子不一致。
5. 本轮是否可能改变任何合法配置的物理结果或输出文件名；若需固定种子逐位对照才能排除，请给最小方案。
6. 阶段 2 三个切片（2A CI 拓扑、2B 屏蔽 shielding_coating 场景的验收标准、2C EffectiveConfig + 模块开关）的设计与验收标准。

## 边界

- 阶段 0 未做改前/改后固定种子逐位对照；Linux 后端 CI 未覆盖；`--inspect-run` 看不到 B1 的校验。
- 阶段 1（文档反向错误、STATUS.md 单一状态源、AGENTS 拆分、证据入库、CI skip 当失败）尚未开始；
  用户已批准“阶段 0 完成后暂停等拍板”，所以现在等你与用户的意见再开工。
