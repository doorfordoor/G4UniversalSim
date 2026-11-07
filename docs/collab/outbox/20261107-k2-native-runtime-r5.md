# K2-3 阻断清单的最小前置修复（r5）

2026-11-07 | 状态：实现与定向自测完成，等待主审独核后冻结新候选

## 1. 两个真实的原候选失败

### F1：`[parallel_world] geometry_config` 的解析语义错误

- 冻结候选 `42be987e` 的 S-A 导出树，按冻结命令从导出根运行：
  `build_vs2026/Release/G4UniversalSim.exe --config project/main.ini --macro project/macros/run.mac --output runs/k2a-1`
  退出码 1，报错：
  `G4UniversalSim fatal error: [parallel_world]/geometry_config does not name an existing file: 'project\project/config/parallel.ini'`
  证据：`out/collab/20261107-k2-build/windows/09-sa-run1.log`。
- 真实消费者：`src/ParallelWorld/ParallelWorldConfig.cc` 的 `ResolveRelative(mainConfigFile_, configured)` 按**主 INI 所在目录**解析该键；材料与主几何仍按进程 cwd 解析。此前“统一按 cwd”的合同解释被该反例否定。
- 导出文件位置不变：并行世界文件仍在 `project/config/parallel.ini`；只有 `project/main.ini` 中 `[parallel_world] geometry_config` 的值应写 `config/parallel.ini`。
- 诊断用的 `main-fixed.ini` 手工副本只用于定位，不作为原包验收证据。

### F2：component 测试闭包缺少真实输入

- 同一冻结候选的导出树，`ctest -C Release -L "^component$" --output-on-failure` 退出码 8：
  `h2_volume_scoring_check` 报
  `Input file does not exist or is not regular: 'scenarios/semiconductor/niel/si_proton.csv'`。
  证据：`out/collab/20261107-k2-build/windows/05-h2-direct.log`、`05-ctest-run.log`。
- 该 CSV 是已承诺组件测试的直接运行依赖，不是可跳过项；手工从工具仓库补文件不能算导出完成。

## 2. 最小修复（只动允许范围）

- `gui/g4usim_gui/core/export_project.py`
  - 新增 `PROJECT_PARALLEL_REF = "config/parallel.ini"`，`rewrite_main_ini` 的 `[parallel_world] geometry_config` 只重写为该值；材料/主几何的重写规则不变。注释说明真实消费者语义。
  - 模板枚举新增唯一数据成员 `scenarios/semiconductor/niel/si_proton.csv`（role=`example`）；缺失时导出模板不可用；其余 `scenarios/` 不进闭包。
  - 模板 manifest 校验允许 `example` 角色；`not_included` 文案写明唯一例外。
- `packaging/export_template_manifest.json`：重算，309 成员，identity
  `1fa4e29430ee813a5736329b9fd2677e178dbac11ceabb289ed828055de8df29`，
  `bytes_total = 3819706`，manifest SHA-256
  `4f512a9d2d453b2c620576cea4f6affe8acccd52579312ebd42e617c1d55c9e8`。
  上一候选身份 `b91e34e4…` 只作为历史记录保留。
- `scripts/test_k2_project_export.py`：对应断言更新为 `geometry_config = config/parallel.ini`；新增导出模板清单必须包含该唯一 `example` 成员、且不得有第二个 example、`not_included` 必须提到 `si_proton.csv`。
- 文档同步（同一事实）：`docs/独立工程导出.md`、`docs/功能支持矩阵.md`（K2-2 行）、`packaging/README-package.md`。

未改：`src/`、`include/`、`main.cc`、CMake、K1 代码、writer、CSV 内容、全局环境；未提交、未推送。

## 3. 定向自测

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 静态导出套件 | `python -B scripts/test_k2_project_export.py` | exit 0；`files=318 identity=bb1829ea38c68cfe template=1fa4e29430ee813a symlinks=yes junctions=yes` |
| GUI smoke | `QT_QPA_PLATFORM=offscreen python -B gui/smoke_tests/smoke_export_project.py` | exit 0，`smoke_export_project: OK` |
| 模板清单自检 | `python -B packaging/export_template.py --root . --check` | `status=ok`，`problems=[]` |
| 文档链接 | `python -B scripts/check_doc_links.py` | 1505 链接 / 531 文件 / 0 断链 |

静态套件覆盖 P1–P8 / R1–R12；其中并行世界重写值、模板唯一 `example` 成员与 `not_included` 例外均为本次新增/更新断言。

## 4. 旧候选在途构建的终态（仅收集，不作新候选证据）

- Windows 受控副本：第一次 build 因复制了缓存而返回 0 但产物未变（真失败，保留）；重新 configure 后构建成功，exe `f311341f…`、`parallelScoringCheck` `22db83b1…`、`h2VolumeScoringCheck` `71c46bd3…`。
- Linux 两份构建（`/home/u123/k2-work/{sa,ctl}`）：exe `e5a9b90f…` / `99026ceb…`；只记录构建终态，不据此完成 K2-3。

## 5. 未执行与下一步

- 未执行：修正后候选的 S-A/S-B 导出、构建、运行、component ctest 与受控修改矩阵；完整 profile；云 CI；安装包；F3 批次。
- 回执：`out/collab/20261107-k2-implementation/author-r5/receipt.json`
  （SHA-256 `7a8db9cf5192340f0567e3a14c550ae778da18426108bb45496d22e729c7e261`，8025 B）。
- 原失败日志与旧回执全部保留；新候选冻结后只补受影响矩阵，不重跑已知无效的旧命令。
