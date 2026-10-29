# 完整 2C 运行时独立只读审查（2026-10-29）

审查对象为 root 尚未构建的工作区候选；未改共享源码，以下为源码级问题与反例，不能当作真实后端回归结果。审查期间 root 已补 generation 对比，本文按读到的新版本记录；行号可能随继续整合移动。

## 需要修复

### P1：finalization 将无事件执行的路径写成 execution_performed=true

`src/Core/EffectiveSimulation.cc:242` 使用 `stage != configure` 判断执行。`src/Core/SimulationManager.cc:574` 对成功 Configure 后的 dry-run、仅打印的 macro、初始化失败收尾同样调用 `WriteEffectiveFinalization()`。因此“/control/echo only”或 dry-run 的最终 JSON 声称执行过。

建议以明确的内核/run/事件事实分列 execution_started、run_started、completed_events（或严格定义现有 execution_performed），不能由文件阶段替代执行。测试至少覆盖 dry-run、仅 echo、仅 initialize、真实 run、run-begin 失败。

### P1：scorer 收据在线程编号映射后被顺序运行过滤掉

`src/Actions/RunAction.cc:131` 传入 OutputManager 的 threadId；`src/Actions/ActionInitialization.cc:22-29` 把负的 Geant4 id 映射到输出编号 0；`src/Core/EffectiveSimulation.cc:196-201` 却用原始 `G4GetThreadId()` 精确过滤。真实 sequential 模式中，scorer 收据 thread=0，快照 thread 为负，成功 BeginRun 证据全部丢弃。

建议收据保留真实 Geant4 thread_id，输出 manager_thread_id 单列（OutputManager 的观察已经这样做）。MT 的 1 worker 不等于 sequential，必须用真正 serial run manager / sequential Geant4 leg 证明。

### P1：native GPS 后索引重排会把实际源的观察挂到错误的命名源

`src/Source/SourceManager.cc:374-377` 的 observePrepared 用当前 GPS vector index 映射 `sources_[i]`；`src/Source/SourceManager.cc:1638-1639` 再由该 SourceSpec 生成字段 path。native source delete/add/clear 之后，index 不再等于原 INI 源身份，例如删除首个 named source 后，第二个 native source 的实际能量被记录到第一个名字的 path。

当前 native unknown 守卫阻止该字段变成 applied，但 raw receipt 的归属本身已失真；未来增加 GPS 读回不能解除 unknown 后直接复用这个映射。建议保存 G4SingleParticleSource* 到原始 SourceSpec 身份的映射（已有 deferredSources_ 的 identity 方法可以参考）；新增 native 源用明确 native identity，不能冒充 INI object。

### P2：configure 导出接口重新捕获 live registry，未返回冻结 configure

`src/Core/EffectiveSimulation.cc:245-250` 只用 configuredEffective_ 做存在检查，实际返回当前 EffectiveSnapshot(configure)。成功命令更新 registry 后再调用该 API，导出的 configure 会含后续 macro/interactive 值，而运行目录里的 effective_config_configure.json 使用冻结对象，两个同名阶段产生不同配置事实。

CLI 当前早期 inspect 路由可避免触发，但公共接口本身不保证不可变。建议从 configuredEffective_ 拷贝，只添加明确允许的 preflight metadata；若要 live configure review 应单独命名阶段/语义。

### P2：receipt 的 failed/unknown 不撤销同 scope 的旧 applied

`src/Core/EffectiveSimulation.cc:213-220` 只写 proven[path]，后续匹配 receipt 若是 failed 或 unknown 就忽略，旧 applied 仍保留；`src/Core/EffectiveSimulation.cc:216-217` 又把除两个识别值外的所有 evidence_level（包含 none 或未知拼写）自动升级为 KernelConstructed。

建议按 (path,generation,thread,run,stage) 定义顺序与有效性；新失败/未知至少撤销同对象 scope 的旧证明，未知 level 不得默认升级。当前各模块回调多以成功观察为主，但 field/biasing 的失败观察与未来真实 observer 会触及此结构漏洞。

### P2：GPS 枚举表达不同导致真实读回永不匹配配置字段

`src/Source/SourceManager.cc:1565` 配置 energy_type 为 mono/gauss 等小写；`src/Source/SourceManager.cc:1644-1646` 直接写入 GPS 的 Mono/Point 等原生枚举。`src/Core/EffectiveSimulation.cc:210` 用严格 JSON 字面量匹配，所以 energy_type 和 position_type 的真实收据永远不能证明本已应用的配置。

建议 observer 保留 native_observed 原文，同时把经过显式、封闭映射的 canonical observed 用于配置比较；不要通用不区分大小写比较任意字符串。energy 数值的直接读回仍可独立证明。

## 已见改进与保留边界

- root 在本次阅读期间已加入 field.configuration_generation 与 receipt.configuration_generation 的匹配（EffectiveSimulation.cc:209-212）；same-value 新来源不能继续仅靠值 hash 认旧收据，这个方向正确。
- run 非空时过滤其他非空 run_id；缺失/null run_id 仍全部纳入。几何构造的持久证据可以有意沿用，但需要明确 lifetime scope 白名单，不应允许未来 event/run observer 缺 run_id 后通配所有 run。
- worker scoring/output 使用 clone ConsumerState，证据列表没有随配置 clone，这是正确隔离；source/physics/field/geometry/material/biasing 共享观察数组靠 ConsumerState mutex 收集、effectiveMutex 序列化快照。目前没有从这段代码证明共享 collector 自身的并发数据竞争。
- effectiveThreadFinals_ 在 header:227 与回调中累积，但没有进入 final metadata。仅保留线程文件，不等于 process final 证明 worker 集合完整；可以加显式收据索引而不提升物理/执行成功。

新增 `scripts/test_effective_lifecycle.py` 是待新构建运行的黑盒门禁，不能拿旧 exe 执行后称候选已通过；本轮只做 Python 语法检查。共享源码由 root 统一修复。
