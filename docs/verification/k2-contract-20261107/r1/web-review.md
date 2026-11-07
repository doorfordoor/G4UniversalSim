# K2-1 独立合同审查（r1 稳定快照）

审查性质：辅助只读第二审查；2026-11-07。依据 `out/collab/k2-contract-independent/r1/identity.json` 所列 16 份快照，核心合同 `docs/collab/outbox/20261107-k2-contract.md`（SHA-256 `a02b4f8baf7b246caefc85b652c9fe846b3bf21fe629a7747030137159b70f4d`）。**结论：现版合同有四项影响 K2-2/K2-3 可执行性的阻断，建议先修订合同再验收。**下列是静态合同/快照源码审查，未作构建或运行。

## 按优先级排序的发现

### [P0 / 阻断] 1. 二级配置路径与导出根目录的运行命令冲突

- **定位**：合同 §4.1–4.2 第 119–135 行、§8.2/8.3 第 266/279 行；快照 `src/Config/ConfigManager.cc:165-179`、`src/Core/SimulationManager.cc:933-938, 983-988`。
- **触发反例**：导出后从导出根执行 `G4UniversalSim --config project/main.ini --macro project/macros/run.mac --output runs/k2a`。此时 `project/main.ini` 中 `[materials] file=config/materials.ini` 指向的是**导出根的模板** `config/materials.ini`，而所选输入实际放在 `project/config/materials.ini`。后端直接取出该字符串并以其检查/载入文件；不存在则拒绝，碰巧有同名文件则可能静默使用错误材料。几何与并行配置也应按其实际解析规则逐一对齐；本快照未含它们的全部加载器，不能声称其解析行为已逐个实证。
- **最小修订**：冻结唯一运行工作目录为导出根，并把三个引用键改为 `project/config/materials.ini`、`project/config/geometry.ini`、`project/config/parallel.ini`，S-B 同规则；或统一改为从 `project/` 运行并改全部 CLI/README/输出路径。为防误读模板 `config/`，加一个故意放入同名不同内容文件的静态/集成反例。无需改后端解析语义。

### [P0 / 阻断] 2. 组件测试选择器实际漏测 H2

- **定位**：合同 §4.3 第 149 行、§8 第 264/277/286 行；快照 `CMakeLists.txt:134-155`。
- **触发反例**：`ctest -R "component"` 按**测试名称**过滤：`parallel_scoring_component` 命中，`h2_volume_scoring_check` 不命中。两者的 `component` 是 `LABELS`，并非两个测试名共有的子串；因此“一次执行两个 component 测试”的验收条件不成立。
- **最小修订**：把 Windows/Linux 命令改为 `ctest ... -L "^component$" --output-on-failure`，manifest 的 `component_ctest_regex` 对应调整为 label 选择字段，断言发现且通过的名称**恰为** `h2_volume_scoring_check`、`parallel_scoring_component`。

### [P0 / 阻断] 3. 预实施模板哈希与正式实现模板哈希混为一项

- **定位**：合同 §3.3 第 89–94 行、P4 第 199 行、§9.2 第 312/315 行、§11 第 345 行；快照 `CMakeLists.txt:158-175,182-198`。
- **触发反例**：K2-2 明确要求修改 `CMakeLists.txt` 增设 standalone 分支、修改 `docs/中文使用手册.md` 与 `docs/Linux构建与验证.md`。三者都属于冻结的 308 文件模板。按协议正常实现后，模板 SHA 必然不再等于预实施值 `1862a858a532f0ff9178c77631308cb2c689bc3dd5f4e683faf2217cdc2110c8`；现版 P4 却硬要求两种来源都等于该旧值，§11 又要求每次计划修改都升合同 r2。
- **最小修订**：旧哈希作为“合同制定时的基线身份”单独留档；K2-2 实现冻结后计算一次正式模板身份，P4 比较**同一正式版本**的 checkout 与 packaged 模板哈希，另确认导出树 `identity.digest` 一致。只有超出授权改动或正式版本再变动时才重新冻结，不用旧哈希否决合同指定的实现。

### [P0 / 阻断] 4. S-B“原样复用 writer 即生成相对路径”的要求缺少现有实现支持

- **定位**：合同 §4.2 第 135 行、§5.1 第 170 行、P2 第 197 行；快照 `gui/g4usim_gui/writers/main_ini_writer.py:128-136` 与 `package_writer.py:155-175`。
- **触发反例**：`create_run_package` 生成 `RunPackage` 时将 `output_dir/materials_ini_path/geometry_ini_path` 均设成 `.resolve()` 的绝对路径；现有 `main_ini_writer` 将它们原样写到 `main.ini`。故“生成时即以相对路径为目标”不是现有 writer 的行为。直接复制进入 `project/` 会触发 R7，且绝对路径指向已清理的 staging。
- **最小修订**：合同明确 S-B 先在隔离 staging 使用现有 writers 生成**绝对路径运行包**，再按白名单字段重写到约定工作目录下的相对路径，随后对最终文件做引用/闭包检查；或定义只影响导出路径生成的明确 writer 参数。应冻结重写键集、路径基准及不修改其它字段的规则。

### [P1 / 判据缺陷] 5. P3 的跨目的地逐字段同一性与 staging 来源审计发生冲突

- **定位**：合同 §4.3 第 142–147 行、§5.1 第 170 行、§5.3 第 198/203 行；`package_writer.py:150-175`。
- **触发反例**：S-B 每次在不同的 `.g4usim-export-<pid>-<rand>` staging 内调用 `create_run_package`，若 `inputs[].original_path` 记录生成文件的绝对 staging 路径，两次导出 manifest 的这一字段必然不同，超过 P3 仅放宽 `created_utc` 和 `original_project_root_audit` 的例外。文件清单的内容 identity 可相同，但“全树除两个字段相同”无法满足。
- **最小修订**：对 generated 输入使用稳定的逻辑来源标记（例如 `generated:materials.ini`，并将临时路径放进单独可忽略的审计字段），或在 P3 明确允许的 manifest 临时路径字段中登记差异；只将 manifest 排除于内容 identity，不能假称 manifest 逐字段一致。

### [P1 / 验收判据风险] 6. statistics CSV 无条件逐字节恒等缺少字段层面的可复现性定义

- **定位**：合同 §7.2 第 237–244 行、§8.4 第 289/291 行；`SimulationManager.cc:713-730` 确认可以在最终摘要 Set 块添加观察字段，且摘要已有时间/执行身份字段。
- **触发反例**：同 seed、单线程的两次运行若统计 CSV 包含 `run_wall_time_s`、`fom_per_s` 等耗时/速率指标，这些字段会随运行环境变化，尽管物理数据不变；将 statistics 与 hits/dose/fluence 一律要求字节相同会造成假失败。当前 16 文件快照**未包含**统计 CSV 写出器，故不能断言具体列确实存在；这是需在执行前消除的判据不确定性。
- **最小修订**：列出需要逐字节一致的真实物理 CSV/列；统计表按物理统计列进行明确比较，运行时间/FOM/执行身份列独立采集并说明允许差异。受控 `summary.Set("k2_export_probe", ...)` 仍须严格单行 diff，`run_summary.txt` 核对新增键；无需因此放宽真正的物理数值判据。

### [P2 / 合同自相矛盾] 7. R7 的 staging 保留与失败统一清理规则冲突

- **定位**：合同 §4.2 第 136 行（“保留 staging 供诊断”）、§5.2 第 183/190 行（“删除并保留诊断”）、§5.3 第 203 行（任何失败 rmtree staging）。
- **触发反例**：含本机绝对路径的 S-B staging 被 R7 拒绝。若保留 staging，则破坏事务清理规范；若按 R7 删除，返回的 staging 路径不存在，无法按 §4.2 原文查看诊断。
- **最小修订**：明确所有失败均清理 staging，仅在结构化失败结果/限定证据位置保留 R7 原因和字段位置（敏感路径可脱敏）；在 R7 中不要同时要求留存临时目录。

## 已审与未审边界

- **已审**：稳定快照合同布局、路径约定、manifest/哈希/P3/P4、选择/拒绝事务、S-A/S-B 合同、独立两平台示例命令、K2-2 修改清单；实际快照中 `ConfigManager` 字符串读取、`SimulationManager` 材料消费及 summary Set 区域、`CMakeLists` 两个组件测试及标签、GUI writers 的绝对路径产生机制、向导默认 spec 的单目标参数。检查仅针对这些明确代码与合同接口。
- **未审**：快照以外的 Geant4 运行时、真实并行世界/计分物理、模板闭包全部 308 文件逐一语义审计、统计 CSV 具体列、两平台 SDK/许可完整链、K2-2 未实现的导出器及其测试；没有实际导出、修改、提交、构建、CTest、模拟或 GUI 操作，也未联系其他代理。
- **状态边界**：此文件是合同静态阻断意见；不表示 K2-1 已关闭，更不表示 K2-2/K2-3 完成。最小修改范围集中于合同的工作目录/路径、CTest selector、模板身份阶段、S-B 路径重写及 P3/CSV/R7 判据。

