# K2-2 独立 Geant4 工程导出：实现交付（待主审独审）

状态：实现与自测完成，**未提交 Git**，等待主审独立复核；K2-3（双平台正式独立构建/受控修改）尚未开始。

## 依据与范围

- 合同：`docs/collab/outbox/20261107-k2-contract.md`（冻结见 `docs/collab/decisions/20261107-k2-contract-freeze.md`，合同 SHA `e27f5a81…`）。
- 仅实现合同 §9 的有限文件集；未改 `src/`、`include/`、`main.cc`、ROADMAP/STATUS/CURRENT/decisions、F3 工具与证据、H8、`.gitignore`。

## 交付内容

- 核心：`gui/g4usim_gui/core/export_project.py`（选择/校验/INI 白名单字节保真重写/事务/模板身份/manifest/verify_export，无 Qt）。
- 模板：`packaging/export_template.py`、`packaging/build_export_template.py`、`packaging/export_template_manifest.json`（310 成员，identity `2c4f39c3…`，算法 `sha256_sorted_sha256_path_lines_v1`）。
- 入口：GUI Project 菜单动作（`window/shell.py`、`window/experiment.py`），Qt-free CLI `export-project`（`experiment_cli.py`）。
- 构建/资源/安装：`CMakeLists.txt` 的 `G4USIM_STANDALONE_EXPORT`（默认 OFF，包裹 m0_* 测试与 scripts 运行时目录）、`build_package.py`/`build_linux_package.py` 生成并校验模板、`installer.iss` 不变。
- 测试：`scripts/test_k2_project_export.py`（P1–P8/R1–R12 + 路径边界反例），`gui/smoke_tests/smoke_export_project.py`，均已注册到 `scripts/run_m0_tests.py`（static `k2_project_export`、gui `gui_export_project`）。
- 文档：新 `docs/独立工程导出.md`；`docs/中文使用手册.md` §15、`docs/Linux构建与验证.md` §10、`docs/功能支持矩阵.md` 行、`docs/开发路线图.md` 记录、`gui/AGENTS.md`、`gui/docs/中文快速使用说明.md`、`packaging/README-package.md`。

## 自测结果（本机 Windows，HEAD `6d7ba12e`）

- 静态：`python -B scripts/test_k2_project_export.py` 绿；profile `static` 50 pass / 0 fail / 0 skip，9213 断言（compiled-component 用例需 `/d/msys64/ucrt64/bin` 在 PATH，属既有本机前置；首轮 7 个失败与 tracked-source 门禁失败日志原样保留）。
- GUI：`smoke_export_project` 绿；profile `gui` 80 pass / 0 fail / 1 skip（`gui_vtk_axes_theme` 缺 PyVista，本机未装 3D 依赖），10823 断言。
- 一次真实 S-A 导出：payload identity `ece2d146…`，template identity matched，manifest 命令与组件测试为冻结显式形式。

## 整体门禁状态（必须如实记录：未通过）

- `static` profile：用例 50/50 通过、9213 断言，但 **exit=1**，`--require-tracked-sources` 门失败：7 个源文件不在 Git 索引；其中 5 个是本任务新增且禁止提交的 K2-2 文件，另 2 个是既有未跟踪的 `tools/collab/deepseek_dispatch.py` 与其测试（非本任务修改，未清理）。日志 `author/logs/run-static.log`。
- `gui` profile：80 pass / 0 fail / 1 skip、10823 断言，但 **exit=1**，`--fail-on-skip` 因缺少可选 PyVista/VTK（`gui_vtk_axes_theme`）而失败；未安装/修改全局环境。日志 `author/logs/run-gui.log`。
- 初次 static 尝试另有 7 个既有编译组件的 PATH/ABI 失败（需 `/d/msys64/ucrt64/bin` 在 PATH），已保留 `author/logs/run-static-before-path-fix.log`。
- 因此：**只有局部专项静态用例与 GUI smoke 通过，完整正式矩阵未通过**；K2-4 负责严格整阶段门。不因门禁环境问题扩功能/测试框架。

## 未执行/限制

- 未对导出树做真实 CMake 构建或 `ctest`（K2-3 范围）；静态测试不是构建证据。
- 未运行完整打包/安装验证、云 CI、F3 性能批次；未重建后端（无 C++ 源变化）。
- 仅支持 S-A/S-B 两个子集与单 run 宏；不导出 GUI/后端/SDK/数据；仓库无项目许可证，不得臆造。
- 模板文件（CMake/文档）后续若再改，必须重生成 manifest 并复跑静态测试。

证据：`out/collab/20261107-k2-implementation/author/receipt.json`、`author/reports/`、`author/logs/`。
