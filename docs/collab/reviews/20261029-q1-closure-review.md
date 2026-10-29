# Q1 关闭前独立覆盖复核

## 基线、权限与结论

2026-10-29 root最终裁决：下文初次审查身份与方法保留，最终代码8ecad66（相对f407仅修绘图来源测试夹具）已完成全部冻结验收；详见文末和[最终报告](../../verification/q1-final-20261029/README.md)。本次工程范围Q1关闭，2C/Q2未完成。

实现 root：`C:/Users/123/.codex/worktrees/effective-config/G4UniversalSim`，本次只读核对 HEAD `f40747a865ce46e23a850920bad23c1f0767e711`。`D:/Geant4/G4UniversalSim` 为独立审计目录，本次未操作。唯一新增文件为本报告；未改源码、测试、其他文档，未构建或重跑专项。

本报告对照 ROADMAP 的 Q1 九域、当前实现入口、正式 runner 清单及现有独立 review，属于关闭前范围核对，不是再次逐行全仓审计。未发现需新增的未闭合确定结果错误、漏计分、假成功或崩溃缺陷；R01–R32 的既有缺陷均有对应修复/拒绝边界与正式回归入口。此初次审查结论本身不替代冻结平台验收；后续完成裁决基于文末实际平台证据。各 review 是追加式历史记录，前部“待实现/待构建”不能替代后续证据；主线checkpoint历史记录中的旧HEAD/会话状态亦不能当当前事实。

当前 runner 实际登记 105 组：static 11、backend 46、gui 31、integration 17。初次审查只核对登记数；现Windows与Linux两个版本均已105/105通过，原始结果由root补入本文末表。

## R32 独立实现/测试复核

- `main.cc:677–702` 先保留 macro preflight 和既有 interactive biasing 拒绝；`main.cc:704–708` 以最终 context 的 interactive/dry-run 值拒绝非 csh 执行，覆盖 CLI 与 INI，不依赖只检查 `options.interactive`。拒绝先于 `sim.Initialize()`（710）和 macro 执行，不存在先执行 sentinel/beamOn 再拒绝的顺序问题。
- `main.cc:1014–1015` 原生 G4UIExecutive 分支已变为防御拒绝；没有 unsafe 开关、没有静默改会话默认。dry-run 不进入会话；显式 csh 仍走原有受审计回调。只读 inspection/export 入口不需要启动原生 UI。
- `scripts/test_interactive_commands.py:35–70` 三反例分别是 CLI 裸 --ui、INI interactive=true、裸 --ui 加合法 echo+beamOn macro，逐项检查 failed/非零/零 run/无 sentinel/无 event CSV；dry-run 同 macro 正例检查零退出、dry_run、skipped_dry_run。既有 clean csh 正例及其失败传播用例保留。
- 已读取 `out/verification/q1-targeted-7/20261029-175350-e4b608c3/report.json`：interactive_commands、biasing_worker_runtime、platform_paths、shielding_analysis 四项均 pass/exit0，合计 3893 个 v3 入口、零断言用例列表为空。该报告为 build7 专项证据，不能冒称当前 f40747a 干净全量或 CI 结果；严格门禁通过记录见 q1-core 后续追加。
- Python 桌面 GUI 的 `core/runner.py:119–121` 通过 config/macro 运行，后端几何控制器通过导出 macro 运行；正常 Run/预览不依赖原生 --ui。外部 INI 主动请求非 csh 会话时明确拒绝符合本边界。此复核未实际操作 Qt，也不称任意内核 API/第三方 UI 均已审计。

## 九域覆盖与边界

以下“无新增确定缺陷”仅指本次对冻结实现、既有发现登记及证据链的复核；最终平台状态已由root按原始报告归档，见文末。

| 审查域 | 实际覆盖与修复 | review / 正式 case 入口 | 未扩大的边界；未闭合确定缺陷 |
| --- | --- | --- | --- |
| 启动/配置/命令 | CLI/INI/macro 优先级、来源、空值/单位/非有限、重复/未知字段；R01 配置切换拒绝与失败传播；R09 材料输入；R26 种子/恢复；R30 重初始化；R32 非 csh 入口拒绝。batch 使用递归 preflight 规范序列，csh 直接命令 alias 解析后守卫。 | q1-core、q1-rng、q1-rng-integration、q1-ui-boundary；config_precedence、config_duplicate_declarations、config_value_finiteness、effective_config_export、macro_plan、interactive_commands、random_command_semantics、run_reinitialization。 | 不提供热重载或完整全模块 EffectiveConfig；无法审计的 csh 动态派发拒绝，原生非 csh 执行明确拒绝；不是任意第三方动态命令安全证明。无新增确定缺陷。 |
| 材料/几何/SD | R03 本体质量及实际副本材料；R04 SD 实际 LV 身份；R09 数值/整数窄化/换算后有限性与官方壳层构造范围；R15 bias 名碰撞拒绝；R23 SD 初始化/context std/unknown 异常收尾；R24 普通 GDML sibling 路径碰撞拒绝。包含普通/布尔/STL/GDML/复制/参数化公开路径与对象身份。 | q1-geometry、q1-field 交叉复核；material_numeric、dose_scoring、geometry_a5、gdml_bias_identity、gdml_touchable_identity、sd_context_failure、geometry_safety、geometry_diagnostics、geometry_roundtrip。 | A5 实验等级不变；assembly、明确不支持的非 normal placement/工具及 GDML 身份歧义拒绝；不是任意病态 GDML 或全部物理材料模型保证。R23 注入不等于真实 OOM/FatalException 恢复。旧 test_q1_geometry_boundaries 为修前审计，不是正式最终 case。无新增确定缺陷。 |
| 粒子源 | GPS 配置映射、实际初级顶点/历史、权重、多源/离子/confine/相空间；R12 isotropic 清旧角范围；R13 延迟配置按实际源身份处理原生覆盖及删除/新增/clear，无法可靠审计的 pending 动态路径拒绝。 | q1-field、q1-findings；gps_sources、config_value_finiteness、command_state_gating，phase-space 路径亦在 gps_sources 与相关后端专项。 | 抽样统计/逐粒子重放自洽不等于完整源物理验证；高级 GPS GUI 编辑器未新增，不把初级数当事件数。无新增确定缺陷。 |
| 物理/场/偏置 | R08 最近显式祖先场解析、共享 LV 冲突/同名歧义；R14 process 大小写；R25 worker TLS operator/真实 wrapped process/完整 EndRun 收据、派生截面失败；R29 步前权重；现有 region/limits 公开路径。 | q1-field、q1-geometry 的 R25/R29 复核；physics_a6、fields_a7、max_step_scope、biasing_targets、biasing_worker_runtime、biasing_step_weight。 | master 挂接计划不冒充 worker 生效；proposal/applied 只证明调用。factor 0.1/1/10 的原生 scorer 同次对账不是全域无偏性/FOM。V02 max_step 粒子适用范围保持；重建和原生 UI 不扩大支持。无新增确定缺陷。 |
| 计分/统计 | Edep/Dose/Fluence/LET/DDD、零贡献、事件历史、权重、溢出/异常、ROOT-only master 合并；R05/R07/R10/R11 归一化与稀疏计数；R06 有限性失败锁存；R29 步前权重；R31 修正不能强制 MT 调度的测试假设。 | q1-core、q1-gui-results、q1-geometry；scoring_numeric、statistical_uncertainty、dose_scoring、fluence_scoring、let_scoring、displacement_damage、scoring_mesh、q1_postprocessing、q1_results_backend、biasing_step_weight。 | V01 原近似公式与小样本/零分母不可用状态保持；不宣称统计覆盖率、重尾/偏置误差全面验证。无协方差的跨 cell 投影不画合成误差；NIEL 数据来源与物理标定分开。R31 不以调度顺序猜 master 覆盖。无新增确定缺陷。 |
| 运行与 MT 生命周期 | Build/Begin/End/finalize 的共享失败、启动失败/跨轮文件保留；R23 context 回调收尾；R25 私有对象寿命/worker 收据；R26 受检恢复；R30 真实 run ID 与重复 Initialize 拒绝；GUI 取消/关窗进程所有权。 | q1-core、q1-field、q1-geometry、q1-rng；run_summary、sd_context_failure、biasing_worker_runtime、random_command_semantics、run_reinitialization、q1_public_paths、live_progress。 | 恢复仅 master 当前线程，未保证所有现存 worker；每事件 restore enable 拒绝。对象按 Geant4 TLS 生命周期清理，不每轮删除未注销 operator。真实设备/进程硬终止并非全部可恢复。无新增确定缺陷。 |
| 输出与后处理 | R02 metadata 失败锁存；CSV/ROOT/JSON 版本/单位、稀疏计数/worker 合并、缺失/陈旧/写失败与发布；R27 manifest 唯一自动来源、复制改基、计划到执行来源一致性；当前 weight 语义迁移。 | q1-output-provenance、q1-gui-results、q1-core；run_summary、root_output、merge_outputs、merge_histograms、output_extensions、output_provenance、output_provenance_backend、gui_output_provenance、q1_postprocessing。 | manifest 无文件内容哈希，不证明未篡改或所有预期 worker 均被上游登记；legacy 无清单明示 unverified，显式离线输入不冒充可信完成。无沙箱/内核动态插件/设备持久化保证。无新增确定缺陷。 |
| GUI 全链路 | R16 原子保存/R17 未知字段拒绝/R18 清旧证据/R19 扫描逐 run 成功/R20 最后预览请求/R21 持有进程关闭/R22 工具路径；writer 子集、inspect、QProcess、进度/结果/绘图/i18n，以及 R27 来源与 R32 原生 UI 区分。 | q1-gui-results、q1-output-provenance、q1-findings；q1_public_paths、gui_run_result、gui_scans、gui_backend_geometry_auto、gui_output、gui_output_provenance、q1_results_backend 及 runner GUI/integration 各专项；真实窗口历史入口 smoke_q1_windows.py。 | 桌面 GUI 不开放后端尚无编辑闭环的规则/高级能力；近似预览不当几何真值，完成/物理正确不由退出码或进度单独判定。当前8ecad66实窗证据已归档，20events success、取消/关窗killed且自有进程停止；历史实窗不替代。无新增确定缺陷。 |
| 构建/平台/测试可信度 | 源/测试/可执行指纹、依赖/平台路径、报告摘要与断言门禁；R28 AST 作用域 v3 保守入口；R31 调度不确定性；正式新增反例登记。 | q1-probe、q1-core；runner_contract、report_evidence、platform_paths、ci_annotations、doc_links、backend_capabilities、geant4_data_locator；scripts/check_report_evidence.py。 | 105 登记数不等于通过；v1/v2 与 v3 不直接比较，同代baseline98/98、79303，候选83770，逐例/总数门禁通过。历史 4e6/98 或其他提交 CI 不替代当前双版本真实 CI。无新增产品缺陷；平台最终证据已闭合，证据范围见文末。 |

## 最终验收事实（root追加，2026-10-29）

| 必需证据 | 最终事实 |
| --- | --- |
| 8ecad66干净Windows Release与全105 | q1-final干净检出，MSVC19.51.36246.0/Geant4 11.3.2 MT+GDML；105pass/0fail/0skip，83770个v3入口，严格门禁通过；[report](../../verification/q1-final-20261029/windows-full/report.json)记录全部指纹与原始日志摘要。 |
| 同代v3历史对照 | 4e6fa7a产品二进制，五项测量overlay明确登记；98pass/79303入口。候选逐项及总数无下降，[比较门禁](../../verification/q1-final-20261029/windows-full/evidence-baseline-gate.log)通过；两个旧失败报告原样保留。 |
| 当前源码Windows实窗 | f6_design实际运行并查看结果/取消截图；保存→生成→20events成功，取消/关窗killed、自有进程全停。[report](../../verification/q1-final-20261029/windows-visible/report.json)，exe SHA688f1a45…与全量相同。不外推高DPI/全显示设备。 |
| 当前源码真实Linux Geant4 11.3/11.4 CI | 8ecad66，run40855144863两版本各105；M0 run40855144672两OS各42；4artifacts SHA匹配，12报告门禁通过，Linux两job篡改负向门禁通过；[收据](../../verification/q1-final-20261029/ci/ci-evidence.json)。 |
| 阶段裁决与归档 | 九域约定审查与R01–R32闭合，当前源码/测试指纹跨平台一致。Q1于2026-10-29完成冻结范围验收；历史偏置结果须重跑，非csh原生执行拒绝，完整2C/Q2/I2扩展不随本阶段完成。 |
