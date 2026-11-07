# H3-2 后端修复 r2 独立复验（2026-11-07）

**结论：修复 r2 仍有两项能够复演的冻结合同违反，暂不建议关闭 H3-2。** 前次材料证明两个静态输入均已修复为字符串 `unknown`，但本轮按主审指定核查真实 PreInit 几何切换与极小正体积交叠，分别发现材料匹配收据陈旧和非零交叠漏拒绝。按本轮停止条件，现已停止扩大源码/自动运行范围，尚未执行三个 backend runner。

## 一、身份、复演范围与证据路径

- 阅读 `docs/collab/outbox/20261107-h3-material-proof-fix-r2.md`、`docs/collab/outbox/20261106-h3-contract.md`、`docs/collab/decisions/20261106-h3-contract-freeze.md`、前次独立审查 `docs/collab/reviews/20261107-h3-backend-fix-r1-independent-web.md`。
- 固定运行程序 `out/collab/h3-independent-r3/bin/G4UniversalSim.exe`，执行前后 SHA-256 均为 `712fe41ddf9bd1c66bfdf3a8b1c51945f70a8d35041d66b9bdd52362a503fd81`。固定组件 `out/collab/h3-independent-r3/bin/parallelScoringCheck.exe` 的 SHA-256 均为 `8a65e8c6b23fcb6fadfcb05fe9f4258312105742b29133764b4b7623f1724b85`。`capabilities.json` 登记源码指纹 `caa650c55c58ee9044fd42b2cf986262dd4b2437f3de814826578db2eb188d52`；本轮未重新构建。
- `out/collab/h3-independent-r3/source-sha256.json` 的 **24 个文件**逐项核对 `source/` 及当前工作区同路径源文件，执行前后均为 **0 处 SHA 差异**；包括 runner、两个 parallel 专项脚本及所审产品代码。全部新输入、stdout/stderr、最终摘要、有效配置与结果 JSON 仅写入 `out/collab/h3-independent-r3/`；未改动产品/测试源码。
- 本轮修复确认：从 r2 `material-negative-repro` **原始四份 INI 字节逐文件复制并核 SHA**，使用新程序分别 dry-run，`self_rotated_water_box` 与 `copper_sphere_descendant` 均 `exit=0`、`status=dry_run`、stderr 0 字节，`/parallel_world/objects/volume:WaterBox/material_matches_mass_world` **精确为字符串 `unknown`**。完整原始输入副本与结果见 `out/collab/h3-independent-r3/material-recheck/<case>/` 和 `material-recheck/results.json`，这两项 r1 阻断已按指定反例消除。

## 二、P1-1：PreInit 几何切换后材料匹配仍采用 Configure 时的陈旧证明

**代码定位及机制。** `src/Core/SimulationManager.cc:983–1009` 在 `Configure()` 时加载 `parallelWorldConfig_`、对当时的 `GeometryManager` 调用 `ResolveMaterials()`。`src/Geometry/GeometryMessenger.cc:100–102,165–166,210–214` 将 `/AIHL/geometry/loadConfig` 暴露为 `PreInit` 可用命令并直接加载新的质量几何；`src/Geometry/GeometryManager.cc:234–266` 确实替换其 root nodes。宏执行中的 `main.cc:941–951,984–990,1063–1073` 在 `/run/initialize` 及 BeamOn 阶段调用动态依赖/运行检查，但 `src/Core/SimulationManager.cc:1343–1364` 的 `ValidateParallelWorldDependencies()` 仅重验 scoring、output、biasing、field、mesh，`ValidateParallelWorldForRun()` 后续核验 ghost 构造、尺寸和参考质量，**均未以已更新的质量几何刷新 `material_matches_mass_world` 的整盒证明**。`src/ParallelWorld/ParallelWorldConfig.cc:681–768` 的证明由 `ResolveMaterials()` 保存到字段，并经 EffectiveConfig 输出。

**实际触发输入。** 本轮独立输入位于 `out/collab/h3-independent-r3/lifecycle-geometry-switch/`。`main.ini` 先加载 `geometry_water.ini`，其中质量侧 `Slab` 为 `20×20×2 mm` 水盒；平行 `parallel.ini` 声明同位置同尺寸水盒。`switch.mac` 三行分别为 `/AIHL/geometry/loadConfig geometry_copper.ini`、`/run/initialize`、`/run/beamOn 20`。新质量文件将 `Slab` 改为相同尺寸和位置的 `copper` 材料，其他几何与材料别名保持受支持的正常配置。实际进程 `exit=0`、stderr 0 字节，摘要 `status=completed`、`run_0_planned_events=20`、`run_0_completed_events=20`；最终有效配置同时记录 `/geometry/config_file=geometry_copper.ini`、`/geometry/objects/Slab/material=copper`、`/parallel_world/objects/volume:Slab/material=water`，但 **`/parallel_world/objects/volume:Slab/material_matches_mass_world` 仍为布尔 `true`**。因此确实完成了新质量几何下的运行，而核验收据保留了旧几何的肯定性证明，违反冻结决定第 13 行「无法证明即 unknown」以及第 7 行配置后入口在实际运行前继续保持约束的要求。

**最小修复。** 将材料匹配证明与当前质量几何的版本/实际节点绑定，在接受 PreInit 几何变更后、任何 `/run/initialize` / BeamOn 前重新验证整个计分盒的质量材料域并刷新有效配置，无法证明则输出 `unknown`。若当前生命周期无法安全刷新，可以在启用平行世界时明确拒绝改变已验证质量几何的 PreInit 命令，保留来源行与非零退出；不能继续沿用 `true`。将上述三行宏与 20 事件输入加入既有专项回归，核对最终质量侧材料、平行材料、证明字段、run 完成和来源。完整 stdout/stderr、run summary、最终及逐 run 快照留在 `lifecycle-geometry-switch/output/`；`lifecycle-geometry-switch/results.json` 保存逐输入 SHA 和关键读回事实。

## 三、P1-2：坐标量级容差吞掉可表示的正体积交叠

**代码定位及机制。** `src/ParallelWorld/ParallelWorldConfig.cc:498–519` 的 `ValidateExpandedVolumes()` 按轴计算交集 `[low,high]`，却用 `kContainmentTolerance × max(1,|low|,|high|)` 判断 `high-low > tolerance`。在距原点约 `1,000,000 mm` 处，`1e-9` 相对容差约为 `0.001 mm`，会将 **真实且可表示的 `0.0005 mm` 正长度交集** 当作无交叠。冻结决定第 11 行要求不同 volume/grid 的**正体积内部交叠在构造前拒绝**，仅零体积的面、边、点接触合法。

**实际触发输入。** `out/collab/h3-independent-r3/overlap-precision-repro/` 中质量世界 `size=2100000,100,100 mm`；平行 `A`、`B` 均 `size=2,2,2 mm` 且 `parent=world`、`sensitive=true`，中心分别为 `(1000000,0,0) mm` 和 `(1000001.9995,0,0) mm`，其 X 内交长度为 `0.0005 mm`，Y/Z 各 `2 mm`，内部交集体积约为 `0.002 mm³ > 0`。运行固定 exe、以该案例为 cwd 执行 `--config main.ini --dry-run --output <绝对输出目录>`，**exit=0**、stdout 含 `G4UniversalSim dry-run completed`、stderr 0 字节、摘要 `status=dry_run`、`parallel_world_volume_count=2`、`output_failure_status=none`；应在 Stage A 被拒绝，却完成了配置。证据为 `overlap-precision-repro/{main.ini,geometry.ini,parallel.ini,materials.ini,stdout.log,stderr.log,results.json}` 与 `overlap-precision-repro/output/run_summary.txt`。

**最小修复。** 对受支持的轴对齐 box 直接按可靠数值区间判定严格正交集，避免将世界坐标大小按比例放大为接触容差；允许 `high==low` 的精确贴边，并为浮点舍入的贴边表达建立谨慎的可复核规则。既有 `parallel_world` 专项加入上述两盒输入，断言前置拒绝；同时保留原面接触通过例。无须更改物理判据或引入新的验证框架。

## 四、已审/自动运行/未覆盖边界

- **静态已审**：r2 B 修复的 `CollectWorldBoxes()` 当前节点 rotation 限制、`ResolveMaterials()` 对无效异材质后代的保守排除；PreInit 宏到 GeometryManager 的真实消费者、动态依赖验证与材料证明缓存；`ValidateExpandedVolumes()` 对正交叠的阈值判据。初步抽查了并行世界注册、copyNo=0、SD/TLS 绑定及收据输出的修复位置，但本轮尚未完成 A–I 逐项独立审查或全量审查判定。
- **真实执行已审**：修复后的两个旧材料反例 dry-run 均得到精确 `unknown`。新增几何生命周期 **20 事件真实运行**完成，证明字段错误地为 `true`；新增数值交叠 **1 个 dry-run** 被错误接纳。每次运行使用指定固定 exe，输入 SHA、过程输出、摘要和有效配置可独立复核。
- **按停止条件未执行**：`run_summary`、`parallel_world`、`parallel_scoring_component` 三个 backend runner；未核验 `run_summary` 的 metadata/generated 同边界与逐 run 收据所有细项，未完成 A–I 余项独审，未运行 H3-4 Welch/正式统计矩阵、Linux/CI 或完整 MT 调度，也未执行构建、提交、产品或测试源码修改。主审/作者此前的通过记录保持原身份，不冒称本轮结果。

**验收建议**：当前 r2 修复需继续保留 **H3-2 待验收/阻断**。优先在原 A、B/E 合同内修复上述两条真实反例，再使用冻结新身份恢复三项 backend runner 和剩余 A–I 独立复核。
