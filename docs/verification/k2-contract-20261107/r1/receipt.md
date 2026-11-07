# K2-1 回执（合同草案 r1，待独审冻结）

- 任务：固定清单 `docs/collab/decisions/20261107-k2-closeout.md` 的 K2-1（真实消费者与独立 Geant4 工程导出合同）。
- 时间（UTC）：2026-11-07T05:47:47Z 侦察快照；回执写于其后同一工作段。
- 工作树：HEAD `e44fb444c81aa8cd787b8ad23d106bb12344c4ab`（`roadmap/Q2-scientific-baselines`），102 项既有 dirty（ROADMAP/CURRENT 属监督端，本项只读，未触碰）。
- 已执行：只读侦察（清单/ROADMAP/AGENTS、真实代码与资源定位、git 身份与文件 SHA-256 计算、模板闭包计算）。**未**构建、**未**导出实际工程、**未**启动 Geant4、**未**修改产品/GUI/CMake/F3 文件、**未**提交 Git。
- 冻结门禁：`ready_for_contract_review=true`，停写等主审独审；独审冻结前不进入 K2-2。

## 交付物（SHA-256）

| 文件 | SHA-256 |
|---|---|
| `docs/collab/outbox/20261107-k2-contract.md`（429 行） | `a02b4f8baf7b246caefc85b652c9fe846b3bf21fe629a7747030137159b70f4d` |
| `out/collab/20261107-k2-contract/author/parameters.json` | `b0b2bb35b84775f60d351dfa8103a3d1926b40c521692f7211a14f26091f45d7` |
| `out/collab/20261107-k2-contract/author/closure-files.sha256`（314 行 / 30941 B） | `c8e2a0b79cb4164fc6ea43d6cfda65ea2ac52f7c5fbadc9facd9ee2bc2fd9157`（即其身份 blob） |
| 本回执 | 报告消息中给出；不纳入合同身份 |

## 关键冻结决定

1. **两个代表项目**：S-A `examples/07_parallel_world_box`（hierarchical + 并行计分世界 + dose/fluence + CSV + 1 线程确定性，6 文件 SHA 见合同附录 A）；S-B 向导 `single_target` 生成式（writers 生成 main/materials/geometry/macro）。
2. **模板闭包**：308 个 tracked 文件（314 清单 − S-A 6），`sha256_sorted_sha256_path_lines_v1` = `1862a858a532f0ff9178c77631308cb2c689bc3dd5f4e683faf2217cdc2110c8`；全清单（含 S-A）= `c8e2a0b7…`。导出必须逐文件核 SHA；打包模板与开发模板必须同身份。
3. **产物布局**：源码/头/CMake/cmake/tools/schema/config/macros/docs/licenses/NOTICES + `project/`（相对路径主配置/材料/几何/并行几何/macro）+ 生成 `README-EXPORT.md` 与 `export-manifest.json`；`export-manifest.json` 自身不纳入身份。
4. **无工具目录依赖**：`project/` 只允许相对路径；绝对来源路径仅作 manifest 审计字段；静态扫描 `D:/`、`/d/Geant4`、`build_vs2026`、`out/collab`、`gui_runs` 残留即拒绝。
5. **实施落点**：K2-2 新增 `core/export_project.py`、`packaging/export_template.py`、`packaging/build_export_template.py`、两条测试；`CMakeLists.txt` 增加 `G4USIM_STANDALONE_EXPORT` 开关（默认 OFF 行为逐字不变），把 `m0_*` CTest 与 POST_BUILD `scripts` 复制隔开；`packaging/build_package.py` 的 `RESOURCES` 增加 `export-template`（Linux 包同源自动覆盖）；GUI Project 菜单 + CLI `export-project`。
6. **两平台验收**：Windows `cmake --preset vs2026-x64` + `Geant4_DIR`/`Qt5_DIR`；Linux conda-forge 11.3.2；导出树用 `-DG4USIM_STANDALONE_EXPORT=ON` 构建，仅 component CTest；受控修改为 `src/Core/SimulationManager.cc` 一行 `summary.Set("k2_export_probe", "k2-controlled-change-v1");`，要求重建成功、`source_fingerprint` 改变、`run_summary.txt` 出现该键、物理输出逐字节不变（不成立即失败保留）。

## 已知风险/待主审裁决

- 仓库根无 `LICENSE`：导出只能声明 `project_code=not_declared_in_repository`，不臆造许可；再分发属用户决定。
- Windows 依赖 Qt5（Geant4 ui_all/vis_all 链接）与 Geant4 前缀内 XercesC 头（GDML 组件）；K2-3 若机器缺依赖记环境阻塞，不删组件规避。
- S-B 2 线程不承诺逐位确定性；确定性观察只用 S-A 1 线程。
- 本合同的模板身份来自当前 worktree；K2-2 若改动任何模板文件，必须申请合同 r2 并重算，不得静默漂移。
- 若 K2-2 需要抽取 K1 helper 到 `export_support.py`，只允许原样移动 + re-export，K1 回归必须全绿。

## 未实现/未验证（明确）

导出器、模板构建器、GUI/CLI 入口、CMake standalone 开关、打包 `export-template/`、两平台独立构建/运行/受控修改、正式回归与云 CI 均为**未实现/未验证**，属 K2-2/K2-3/K2-4；本回执不主张 K2-1 之外任何完成。
