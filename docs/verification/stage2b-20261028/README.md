# 阶段 2B 验收证据（2026-10-28）

本目录是可复核的统一测试平台证据副本。`out/` 被 `.gitignore` 忽略，因此把报告与全部日志复制到这里；
`python -B scripts/check_report_evidence.py --report-root docs/verification/stage2b-20261028` 在干净克隆上也能通过。

## 报告事实

| 项 | 值 |
| --- | --- |
| 报告 | `report.json`（`G4UniversalSimM0TestReport` v2，profile `all`） |
| 用例 | **87 pass / 0 fail / 0 skip**（static 10 / gui 27 / backend 35 / integration 15） |
| 断言 | `assertions_executed_total = 116636`、`assert_sites_total = 2688`、`cases_with_zero_assertions = []` |
| 源码指纹 | `5bd97ec5e96e85f83b35b6d33d82ea12493e9d2eb4d78902c8d2ba5165d13206` |
| 测试内容指纹 | `dcc894598eaa69df33ccc87acfbf98e27160640f6e31bc76d2257d2d99d7449a` |
| Git | `git_head = 402a9f264da674c554b32b344ce0a4f75b74603c`，`git_dirty = true`（运行时含本阶段未提交的文档与守门脚本；代码提交为 `402a9f2`） |
| 后端 | `source_sha256_manifest_matches_executable`；MSVC 19.51.36246.0、Geant4 1132、MT |
| exe | `build_vs2026/Release/G4UniversalSim.exe`（1 734 656 B）SHA-256 `dd62fd8748fba532a12842881b0a680dff11816a6031724fd4caf9ecd83cde1f` |
| 日志 | `logs/`（87 个，摘要与报告一致，LF 字节） |

## 本阶段新增/变化的用例

- `shielding_scenario_model`（static）：命令行生成器提炼成 `scenario_model.py` 后的文件集合、确定性、字段校验、CLI 与模型逐字节一致、兄弟场景生成器可导入。
- `shielding_analysis`（static）：`analyze(output_dir)` 的正常值与五类 `EvidenceError`。
- `scenario_shielding_core`（backend）：headless 驱动的 15 字段校验、真实 200 事件运行、证据标签、缺统计文件与缺可执行文件的失败。
- `scenario_page`（gui）：Scenario 页字段划分、高级切换、校验、生成、证据列、中英切换、缺失可执行文件提示。
- `gui_scenario_backend`（integration）：12 步端到端（offscreen Qt + 真后端 200 事件 2 线程），结果表证据列、摘要核对、日志与证据面板。
- `platform_paths`（static，守门）：测试脚本不得写死 `build_vs2026` 构建路径——提到它就必须同时读 `G4USIM_EXE`。

## 复现

```
python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip --report-root out/verification/stage2b-20261028
python -B scripts/check_report_evidence.py --report-root out/verification/stage2b-20261028
python -B scripts/test_shielding_coating.py        # 含 analyze.py 五种缺证据反例
python -B scripts/test_scenario_shielding_core.py # 需要真实后端（读 G4USIM_EXE）
python -B gui/smoke_tests/smoke_scenario_backend.py
```

## 这份证据不证明什么

- 只覆盖本机 Windows（MSVC + Geant4 11.3.2 MT）；Linux Actions 的四 profile 结果见 `STATUS.md` 的 CI 段。
- 断言数是已执行断言的下界，不是覆盖率；断言总数不下降与零断言列表为空是本项目的验收阈值。
- 本场景不是新的物理基准：TID/DDD 的定义与容差沿用 B2/B3；只验证法向入射平板几何与 15 个字段。
- 未验证非法向入射、非平板几何、光核/活化、极薄层失效，也未做 Geant4 11.2/11.4 兼容矩阵。
