# H3-2 后端修复 r1 独立复验（2026-11-07）

**结论：发现 P1 阻断缺陷，修复候选暂不建议验收。** 修复回执 A–I 中的 B「整盒材料一致性证明」仍有两个可执行配置反例。两例均使用固定 r1 程序，正常完成 `--dry-run` 并在真实 `effective_config_finalization.json` 中错误地给出 `material_matches_mass_world=true`，按冻结决定应为 `unknown`。遵照本轮停止条件，**未继续 A–I 广泛审查或执行三个 backend runner**。

## 1. 身份、环境与方法

- 阅读了 `docs/collab/outbox/20261106-h3-backend-fix-r1.md`、`docs/collab/outbox/20261106-h3-contract.md`、`docs/collab/decisions/20261106-h3-contract-freeze.md`、`docs/collab/reviews/20261106-h3-backend-independent-r1.md` 以及前次辅助审查 `20261106-h3-web-independent.md`。依据冻结决定第 13 行，只有整个平行计分 box 对应的质量材料域已被证明一致，才允许输出 `true`，其余记 `unknown`。
- 固定程序 `out/collab/h3-independent-r2/bin/G4UniversalSim.exe` SHA256 前后均为 `e442d894550940b8c75b6ce98ee6ae089553e4b02ae6361c2f69b06468bc0dc0`；固定组件 `parallelScoringCheck.exe` SHA256 前后均为 `db70c3f50dc23e1cdc96157b3761c8d628939f11302a9f0d2657bac16c92eaa6`。`source-sha256.json` 的 24 个文件逐项复核，执行前后均与 `source/` 快照及 D 盘当前对应文件完全一致（0 差异）；runner 与 `test_parallel_world.py`、`test_parallel_scoring_component.py` 同样逐项匹配。`identities.json` 登记源码指纹 `dda9ff21e4464a57aaa6838609c9a27aaeb66706b162105117da158b4adf3d8f`，本轮未以构建重算该指纹。
- 两例输入依据项目 `GeometryConfig::ParseVolumeSection` 支持的 `rotation = 0 deg, 0 deg, 90 deg`，以及 `shape = sphere`、`parameters = rMin,rMax,startPhi,deltaPhi,startTheta,deltaTheta` 格式编写，均通过实际配置解析。复制到独立 `out/collab/h3-independent-r2/material-negative-repro/<case>/`，以各案例目录为工作目录，使用 `--config main.ini --dry-run --output <该例绝对输出目录>`。完整输入、`stdout.log`、`stderr.log`、`output/run_summary.txt`、`output/effective_config_finalization.json` 已分别保存；总体记录见 `out/collab/h3-independent-r2/material-negative-repro/results.json`。

## 2. P1 阻断发现：材料匹配证明忽略节点自身旋转和无法投影的异材质子节点

**位置**：`src/ParallelWorld/ParallelWorldConfig.cc:605–629` 的 `CollectWorldBoxes()`；`:666–744` 的 `ResolveMaterials()`。冻结快照为 `out/collab/h3-independent-r2/source/src/ParallelWorld/ParallelWorldConfig.cc`。

**机制 1（当前候选自身旋转）**：`:615–619` 为当前节点设置 `valid` 时检查了祖先的 `transformProven`、box 形状与正常 placement，但**漏掉 `IsIdentityRotation(node.rotation)`**。该检查只出现在 `:627–629` 构造 `childrenProven` 处。因而旋转的当前盒仍使用未旋转的 `offset ± size/2` 投影作为质量世界材料域，在 `:715–719` 被选择为包含同材料的候选。

**反例 `self_rotated_water_box`**：质量世界 `WaterBox` 为 `size=20,2,2 mm` 水盒，绕 Z 旋转 90°，中心位于原点；平行 `WaterBox` 为相同声明尺寸但未旋转。实际质量水盒在世界坐标的横向长边沿 Y 轴，平行盒长边沿 X 轴，平行盒相当大一部分落在质量世界真空内，整盒对应材料显然无法证明一致。程序结果为 `exit=0`、`status=dry_run`、`stderr.log` 0 字节；有效配置字段 `/parallel_world/objects/volume:WaterBox/material_matches_mass_world` **解析值为布尔 `true`**，原因为 `matched by declared mass-world box 'WaterBox'`。冻结合同要求 `unknown`。

**机制 2（无法投影的异材质后代）**：`:729–736` 在排除不同材料与计分盒正体积交集时直接 `if (!other.valid || other.material == material) continue`。非 box（例如球体）被 `CollectWorldBoxes()` 标为无效，且在此处被**无条件跳过**；即使它是同材料候选的内部异材质 daughter，也不会阻止 `:738–742` 签发 `materialMatchesMassWorld=true`。

**反例 `copper_sphere_descendant`**：质量世界中 `WaterBox` 是 `40×40×2 mm` 水母盒，中心处有铜子体 `CuSphere`，其合法配置为 `shape=sphere`、`parameters=0 mm, 0.5 mm, 0 deg, 360 deg, 0 deg, 180 deg`，`parent=WaterBox`；平行 `WaterBox` 为相同尺寸/位置的无旋转水盒。铜球完整位于计分域内，母盒空间的质量输运材料并非处处为水。程序结果同为 `exit=0`、`status=dry_run`、`stderr.log` 0 字节；同一材料匹配字段**解析值为布尔 `true`**，原因为 `matched by declared mass-world box 'WaterBox'`。冻结合同要求 `unknown`。

| 案例 | 完整证据目录 | exit | stdout 完成标记 | 有效配置字段（实测） | 合同预期 |
| --- | --- | ---: | --- | --- | --- |
| `self_rotated_water_box` | `out/collab/h3-independent-r2/material-negative-repro/self_rotated_water_box/` | 0 | `G4UniversalSim dry-run completed` | `true` | `unknown` |
| `copper_sphere_descendant` | `out/collab/h3-independent-r2/material-negative-repro/copper_sphere_descendant/` | 0 | `G4UniversalSim dry-run completed` | `true` | `unknown` |

**最小修复范围**：

1. `CollectWorldBoxes()` 中当前节点的 `valid` 条件加入自身旋转为恒等的检查；沿用既有保守证明，不必实现旋转 box 的一般世界坐标包围盒算法。
2. `ResolveMaterials()` 证明同材质候选时，枚举其后代。遇到不能可靠投影/排除交叠的异材质或材料身份不明的后代，保持 `unknown`；不得将 `!other.valid` 直接当成「该区域不存在」。能够证明与计分域无内交集的后代可放行，未知位置/形状时优先保守降级。
3. 在既有 `scripts/test_parallel_world.py` 回归中加入上述两个合法输入，检查真实 finalization 字段精确等于字符串 `unknown`，并保留原有同材质未旋转叶盒 `true` 正例。再由单写者实施修复和复测。

## 3. 已审／未审边界与状态

- **已完成**：修复回执、冻结合同和首轮主审意见的定向核对；固定程序与组件 SHA 前后核验；24 个源码快照 manifest 项及 D 盘产品/脚本一致性前后核验；修复 B 的 `CollectWorldBoxes`/`ResolveMaterials` 静态审查；两个真实配置 `--dry-run` 负例及最终有效配置文件读取。两次摘要均为 `status=dry_run`，stderr 为空，未出现 `Access is denied`。复验没有覆盖事件输运、真实 SD 命中或运行后剂量数值。
- **按阻断停止**：没有运行 `run_summary`、`parallel_world`、`parallel_scoring_component` 三个 backend runner，也没有完成 A、C–I 的独立全量审查。未构建、未执行 H3-4 统计批次、未改产品/测试源、未提交或联络其他 agent。修复回执自报的既有通过成绩保留为作者证据，**本轮没有独立确认**。
- **裁定建议**：H3-2 修复 r1 的「材料整体匹配」B 仍不满足冻结合同，第 13 行要求的 `unknown` 被错误记录成已证明 `true`，因此当前候选保持 **待验收／阻断**。先由单写者修复 B，再恢复 A–I 复验及三个 backend runner。
