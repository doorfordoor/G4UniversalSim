# Q1 GUI / 后处理审查与修复

## 独立 GPS 生命周期复核：确认阻断（2026-10-29）

只读复核 SourceManager/main.cc/test_gps_sources.py。**csh alias 展开绕过 BeforeNativeGPSCommand，有真实错误成功结果，需修复后再冻结。** pending 配置为 C12 ion charge2、12MeV，输入：

```
/control/alias pc /gps/particle
{pc} proton
/run/initialize
/run/beamOn 2
exit
```

现有候选 exe SHA256 `4cca89890ffbce252623f682639d7d1597f7a0f99dc31d5c8c49c8b4388e9a84` 实际 exit=0，两个首步 particle 均 C12，而不是显式原生覆盖的 proton。证据 `out/q1-gps-independent/report.json`、`alias.log`、`alias/hits_t*.csv`。该二进制属于第一轮候选，最新源码仍有同样路径：BeforeNativeGPSCommand 只拒绝 execute/loop/foreach，`/control/alias` 本身及 `{pc}` 都不命中 `/gps/` 前缀，Geant4 ApplyCommand 展开后修改 GPS，PrepareForRun 再把未标记 overridden 的 INI ion 写回。

建议在 pending deferred 配置期间明确拒绝无法审计的 alias/带替换引用命令及其他动态 control 执行路径，或在执行前审计最终展开命令；不能仅禁止创建新 alias，因为 batch/先前命令可以已有 alias。最小回归须包含上面的实际 alias 成功但粒子错误反例、预先存在别名引用、明确失败摘要/非零及后续命令不执行。`/control/if` 等动态派发也应按实际命令集合审计，不能声称仅三个名字已完整封闭动态入口。

其余检查结论：
- 按 GPS source 指针而非索引登记延迟配置，delete 前擦除对应指针、clear 清表，避免 index 移位/地址重用回放旧配置；PrepareForRun 遍历当前存活源且不改变 current-source 选择，第二轮 deferredApplied 保护 native 改动。
- 覆盖标志在 ApplyCommand 前写入，但 ApplyCommand 失败会 fail-fast 停止并写失败结果；在受审计直接命令路径中没有发现“失败命令后继续跑”的新缺口。
- 单字段 setter 未改成全量重放，单源原生 energy 与配置 particle 的隔离仍在；isotropic 显式清 theta/phi 是有对应输出方向反例的定向修复。
- 新 source_interleave_cases 确实启动真实 exe、读取 first primary step，并对第二轮 _r1 文件显式计数：直接 particle 覆盖的初始化前后、双源选择/删除新增/clear、第二轮能量、不审计 UI 拒绝均真正触达修复。并非字符串测试或空集合通过。
- csh 的 nested 用例使用 missing.mac，但要求专属 pending ion/confinement 文本，因此确实证明前置拒绝，不会被“文件不存在”误充通过；它没有覆盖 alias、动态条件命令。延迟 confinement 被原生 confine 覆盖的分支也尚无新增专项，只能作为覆盖边界，不把普通 confinement 原有测试算该交错路径验收。

未修改 C++、GPS 测试或其他共享文件。这里不审查物理模型数值。

## R22 提案与判据

产品选择自定义 backend 后，合并计划按显式 merge_histograms_exe → 存在的所选 backend 同目录精确工具名 → 原 workspace 回退的顺序发现。`.exe` backend 对应 `mergeHistograms.exe`，无后缀 backend 对应 `mergeHistograms`；不扫描任意可执行文件、不改显式路径（即使其不存在也不悄悄回退）。项目加载、路径编辑与生成前同步 backend。回归覆盖两平台后缀、显式优先/失效、邻接缺失回退、无关 exe 不匹配和页面调用点。

实施完成：`output/merge_plan.py` 新增 keyword-only backend_executable；`widgets/output_page.py` 缓存并传递选择；`window/project.py` 的加载、路径编辑、运行前同步三处接入。显式参数仍原样最高优先。`smoke_output_tools` 31 执行断言通过；`smoke_q1_public_paths` 新增真实页面邻接发现，38 执行断言通过；`smoke_main_window_ui` 通过。此次未无变化重复 Windows 生命周期。

## 独立只读 C++ 数值审查

检查 NumericChecks、HistoryStatistics、ScoringManager、OutputManager、RunAction 失败捕获和 main beamOn/最终收尾检查：有限性在乘加前后检查；事件矩和 worker 合并在 candidate 成功后提交；共享 firstFailure 互斥锁存，Begin/EndEvent 及 scorer 异常转停止；master 在 CSV/ROOT mesh 发表边界验证，失败后不发表 scorer statistics；CSV v2 仅追加 uncertainty_estimator/status，原列顺序、零哨兵、既有近似公式维持。没有新增确认的 C++ 阻断。部分文件可能已创建但未登记的失败路径仍必须由 failed 摘要阻止被当作有效结果，不能凭文件存在认为成功。

发现并修复关联 Python 数值不一致：ROOT helper 原 `sum**2` 在 total=2e154、sum_sq=1e308、N=8 时溢出，C++ 已避免。Python total/ratio/mesh 均改为等价分步除法；补大有限矩反例，`test_q1_postprocessing` 通过。未改变估计方法。

本地现成 scoringNumericCheck.exe 返回 checks=32，而当前源测试声明 checks=38；这是旧构建证据，不能称当前 C++ 单元已验收。主负责人冻结重建后须重跑 test_scoring_numeric 及平台证据门禁。未构建、未修改 C++。

## R16–R21 已授权修复范围与验收判据

- R16：同目录临时文件写完、flush/fsync 后原子替换。序列化/写入/替换任一步失败保留原文件，清理临时文件；成功可重新加载。
- R17：拒绝未来/非法项目版本和不支持的未知字段（含嵌套），不实现 E6 迁移；现有支持字段往返保留。拒绝错误指出字段路径，不静默丢弃。
- R18：每次刷新清空旧摘要、日志和合并计划；无目录/坏目录不显示上一轮结果。
- R19：扫描 success 至少必须有正事件数、完整逐 run 一致性与后端成功摘要；run_status 的 success 不可覆盖无效摘要。零/缺失/矛盾计数不得 success。
- R20：只有最后请求对应的结果/失败可发布；缓存命中、等待请求取消、停止后均不得被旧完成回调覆盖。
- R21：窗口关闭取消本窗口的主 run、scan 队列、geometry/inspect、merge 队列、输出扩展及场景子进程；有界等待后 kill，确认停止才关窗。仅操作持有的 QProcess，不按名称杀其他应用。真实 Windows 可见窗口验证保存/生成/运行/取消/关窗/新结果身份并截图。

工作目录：`C:/Users/123/.codex/worktrees/effective-config/G4UniversalSim`。原目录只读。未提交、未构建 C++、未修改共享契约文档。

## R16–R21 实施及复核（13:48 更新）

最终复核：`out/q1-gui-review/20261029-134745/report.json` 对最后代码 PASS；正常20事件 success，取消及关窗 killed，owned_processes_stopped=true，dialogs 仅生成包原有警告，没有预期 kill 的 Crashed 弹窗。已直接查看该轮 cancelled.png：Run Console 显示 killed、Stop/Kill 禁用、底栏明确 User requested process termination。最后 `smoke_q1_public_paths` 再跑为 37 断言通过。无运行中的测试会话。新增 runner 建议名称 `q1_public_paths`（GUI profile）；`q1_windows` 仅 Windows 可见窗口专项，不放 Linux CI。完整 Q1 仍须主负责人冻结后的全量证据门禁。

上述六项已实现，新增 `gui/smoke_tests/smoke_q1_public_paths.py` 为验收回归；原 audit 脚本保留修复前反例语义，不应注册为绿色测试。回归 37 个执行断言：序列化失败/原子替换失败保持原字节且无临时文件残留；中文项目正常读写；未来版本/顶层与嵌套未知字段拒绝；坏目录旧摘要清除；零事件及有 success 状态文件的零事件、逐 run 不等但合计相同均不得 success；缓存命中/等待撤销/stop 后过期预览不发布；main/scan/geometry/inspect/merge/extension/scenario 真实持有子进程全停止、队列清空，同时独立对照进程仍存活。

`smoke_project_io`、`smoke_scans`、`smoke_hier_boolean_geometry_editor`（仅 Python 部分）、`smoke_source_field_preservation`、`smoke_output_tools`、`smoke_main_window_ui`、`test_q1_postprocessing` 通过。旧扫描合成摘要已补足正常后端的逐轮生命周期字段。以上为定位与专项，仍待统一冻结的全量报告。

hist_raw 原失败已定位为测试环境缺省工具路径：传 `G4USIM_MERGE_EXE=out/build-effective/Release/mergeHistograms.exe` 与候选后端后，`smoke_geometry_backend_package` 完整通过（simple/layered/hierarchical/双worker）。产品 `find_merge_histograms` 仍只搜仓库常规 build/bin 路径，未使用用户所选 backend 的同目录；out/build-effective 不是其搜索路径。此为自定义构建位置的工具发现限制，未将环境修复冒称产品已支持任意同目录工具。

可见 Windows 验收脚本为 `gui/smoke_tests/smoke_q1_windows.py`（必须 QT_QPA_PLATFORM=windows 与 G4USIM_EXE，不加入 Linux/offscreen profile）。通过记录 `out/q1-gui-review/20261029-134632/report.json`：候选 exe SHA256 `4cca89890ffbce252623f682639d7d1597f7a0f99dc31d5c8c49c8b4388e9a84`，真实窗口 exposed；保存/重新加载→生成包→20事件 success→新 output/summary 哈希→长运行停止后强制结束→另一次运行关窗强制结束，持有 QProcess 全 NotRunning。截图 results/cancelled/before-close 保留。已直接查看 results.png：Results 页显示新目录、24个文件与 success，未仅凭路径声称视觉检查。

首轮 134354 因脚本仅调用 terminate 后等待超时而失败，已确认无遗留后端才重跑；Windows console backend 可不响应 terminate，界面既有 Kill 是必要后续。134632 运行暴露预期 Kill 引发 QProcess Crashed 弹窗：已在 MainWindow 对明确 stopped/killed 的 Crashed 过滤弹窗，最终状态仍由 runner 写 stopped/killed；关窗合并进程错误也不弹阻塞对话框。正在以最后版本重跑可见窗口，不能用较早截图代替最后代码验收。

## R-05

反例：完成 4 个事件、合计值 12（事件可以有不同初级粒子数），旧代码输出 3 却标 `/ primary`。现在 `build_plot(normalization="total"|"per_event")`；旧 positional/keyword `per_primary=True/False` 保留旧数值并发 DeprecationWarning、附可见 notes，新旧参数冲突拒绝。默认 total 不变。pulse 本来就是事件分数，不再次除计数。

PlotPanel、ScanPage 改用 per_event 控件与标签；map 色条标明 / event。绘图 CSV 末尾追加 normalization、value_label 两列（既有列名不变），bar/profile 合并保持归一化字段。扫描导出按当前选择归一化并在 unit 标 / event；缺正完成数时拒绝绘制/导出，界面显示理由。场景模块具有独立的 per_primary 契约，未机械替换，原 i18n Per primary 保留。

## R-07

反例：worker 0 有 2 个历史且产生一行 sum=2、sum_sq=4；worker 1 有 2 个全零历史而无行。旧 ROOT helper 以 N=2 给出 sqrt(0.5)，正确总历史 N=4 对现有公式为 sqrt(0.75)。未更改统计估计公式。

scorer 与 mesh 的分母统一要求同 run 的 run_metadata_json_v1 或显式 n_events。稀疏行仅用于一致性及下界检查；不以可选 events 树或 histogram entries 推断完整历史数。显式计数须非 bool 非负整数（含 numpy Integral）；元数据损坏、重复 run ID、非整数、显式冲突、贡献 worker 计数不一致/总数大于可靠分母皆拒绝。零事件仅接受空 scorer 行，正常全零但 N>0 返回空结果。`load_mesh(..., *, n_events=N)` 为新增参数，旧可靠 metadata 调用保持。

注意：metadata 缺失的 standalone ROOT 即便存在 events 树也需显式计数。邻接 metadata 存在而损坏时不能以显式参数掩盖损坏。非标准 ROOT 文件名在邻接 metadata 存在时不能辨识 run，会明确拒绝。

## 本轮验证

- `python scripts/test_q1_postprocessing.py`：PASS。合成 ROOT sparse worker、events 树有/无、metadata 有/无/损坏/非整数、显式 bool/小数/负值/字符串/冲突、两 run、全零与空结果；Edep/Dose/Fluence 按事件值与误差、旧 API 警告/冲突、导出字段。
- `QT_QPA_PLATFORM=offscreen python gui/smoke_tests/smoke_plots.py`：PASS。新增 per-event 曲线与 map 色条检查，原 PNG 导出保持。
- `QT_QPA_PLATFORM=offscreen python gui/smoke_tests/smoke_scans.py`：PASS。新增归一化导出单位、轴标签和缺计数拒绝检查。
- py_compile：PASS。

这不是本轮真实多初级粒子物理验收。主代理需将 `test_q1_postprocessing.py` 纳入统一平台，并用实际候选后端完成真实 1/2/变粒子数历史、单/多 worker、ROOT/statistics 对账。`test_root_output.py`、`test_statistical_uncertainty.py` 未修改（主代理独占）。ROOT helper 的 mesh 同样受影响，真实 plots backend 与 root output 测试须纳入复核。

## 后续实证与当前结论（覆盖上文旧待办）

已按 V01 决定实现 IO/GUI 的 `uncorrected_event_moments_v1` / `uncorrected_delta_ratio_v1` 与 availability/status。保留原数值公式与旧零哨兵；N<2、zero_total、undefined_ratio 的误差在 GUI/导出中不可用，不画零误差条。新旧 CSV、ROOT 与 N0/1/2 反例已加入 `test_q1_postprocessing.py`；该测试及 smoke_plots/smoke_scans 在最后修改后通过。ROOT 实际 n_events 列为 double，内部计数接受有限、精确整数的浮点表示，显式 API/JSON 仍严格要求整数。

R10 已阻止 LET ratio 按事件再除 N；R11 对聚合多个 cell 的 profile/map 隐藏误差（原始事件协方差缺失），只有未聚合的 cell 保留其可用误差。未改物理数值或默认估计公式。

真实基线证据：`out/verification/q1-results-baseline-03/report.json` 保留修复前反例，`q1-results-baseline-04/report.json` 为修复后通过。基线 exe SHA256 为 `f78fa2fb06c08dbebd590bf7457f306ec85d9d6a7a8c0f0b30f5b7daeb6b45e1`，不是本次候选 C++。实际 4 事件的初级粒子数分别 4/8/7；32 事件的稀疏输出只有贡献 worker 的 4 事件，正确分母为 32；event_edep 开/关及全零 worker 均覆盖。原始逐事件跨 cell 得到投影误差 4.472278，忽略协方差为 3.162378。旧 LET 1.37366 曾被除 4 成 0.3434，现在拒绝。脚本 `scripts/test_q1_results_backend.py` 使用 G4USIM_EXE，需主负责人注册 runner。

此前完整 GUI profile 为 29 pass / 0 fail / 0 skip、1997 断言：`out/verification/q1-gui-audit/20261029-132414-57618bc2/report.json`；发生于最后 V01 修改之前，不能冒充当前完整验收。最后版本真实 plots/scans backend 两项通过（`out/q1-plots-backend.log`、`out/q1-scans-backend.log`）。补充 9 项集成审查为 8 pass / 1 fail：`out/verification/q1-gui-integration-baseline/report.json`。失败在 smoke_geometry_backend_package.py:184，双 worker 没有 available hist_raw merge task；前面三类几何真实运行通过。尚未判定其是稀疏 worker 偶发条件还是既有合并实现缺陷，不能抹去失败。

## 新确认阻断：需协调额外生产文件单写者

`gui/smoke_tests/audit_q1_public_paths.py` 是反例复现而非绿色验收测试；输出 `out/verification/q1-public-paths.json` 确认以下六项。当前未修改这些额外生产文件，请主负责人分配修复所有权，不能作为 Q1 后隐含错误保留：

|问题|文件|实际反例|
|---|---|---|
|保存非事务性|core/project.py|注入 json.dump 写错误后原项目已被截断，无法保留原文件|
|未来格式/未知字段静默损失|core/project.py|version999 被接受，再保存降为 version6 且未知字段消失|
|陈旧结果残留|widgets/output_page.py|从有效输出切到不存在目录，旧摘要仍显示|
|零事件假成功|core/scan.py|collect 接受零事件摘要为 success|
|预览异步过期结果|preview3d/backend_geometry_controller.py|B 执行中请求缓存 A，先发布 A，B 完成后又发布过期 B|
|关窗不收尾主运行|main_window.py|close() 后主 runner 子进程仍存活；测试显式清理了进程|

## GUI 公开路径覆盖索引与缺口

下表按公开入口列出生产路径与已有测试；通过既有测试不代表异常链路全覆盖。

|公开路径/文件组（相对 gui/g4usim_gui）|已有 smoke / 本轮覆盖|缺口或结论|
|---|---|---|
|widgets/start_page, project_page, run_history_page; core/project, paths; main_window|start_page/project_io/history/main_window_ui + 新 public_paths|保存失败、未来版本、关窗已确认阻断；坏 JSON 既有测试不能覆盖写中断|
|widgets/new_simulation_wizard; core/wizard; widgets/config_builder_page|new_simulation_wizard/new_simulation_backend|生成至真实运行通过；不是所有路径权限/磁盘故障验收|
|widgets/config/*; core/config_schema; config reader/writer|config_editors/run_config_editors/source_editor_v2/source_field_preservation/materials_editor/geometry_editor/hier_boolean_geometry_editor|基础 editor→writer 保留/拒绝契约已有测试；独立文件未知字段与保存事务仍需修复项目层|
|widgets/effective_config_page; core/effective_config/backend_capabilities|effective_config/run_input_modes|inspect 与生成/导入模式通过；取消、失败状态需结合主负责人最新后端再验|
|widgets/run_page; core/runner/run_result/run_progress/log_parser|run_result/live_progress/live_progress_backend/run_input_modes|单项运行/终止已有覆盖；主窗关闭反例尚未修复|
|preview3d/*; widgets/config/preview3d|3d_view/preview3d/preview3d_primitives/backend_geometry/backend_geometry_auto/source_glyphs/trajectory_view|缓存异步竞态已确认；geometry_backend_package 的 hist_raw 断言失败待归因；无本轮人工屏幕视觉验收|
|widgets/output_page/plot_panel; output/*; scripts/g4usim_io.py|output_tools/output_extensions_gui/parsers/dose_results/fluence_results/plots/plots_backend + q1_postprocessing/results_backend|新旧数据/归一化/误差已补；切换坏目录残留摘要仍阻断；merge hist_raw 失败待查|
|widgets/scan_page; core/scan/scan_runner|scans/scans_backend + public_paths|归一化导出已原子写；core.collect 零事件假成功仍阻断|
|widgets/scenario_page; core/scenario_shielding|scenario_page/scenario_backend|真实基线通过；独立 per_primary 契约未在本次机械改名|
|core/i18n/theme/icons; widgets/ui_helpers|main_window_ui 与各 page smoke|新增提示已翻译；不宣称全部布局/可访问性/语言切换实屏验收|

## DeepSeek 独立复核及核对

从既有 out/collab/workspace_design_request.py 核实 provider `https://api.deepseek.com/chat/completions` 与模型 `deepseek-flash` 后，使用指定密钥文件只提交必要 GUI 代码片段。响应保存在 `out/collab/q1-gui-independent-review.json`，返回模型 deepseek-flash，response id `5c289ddf-9cda-473e-8e9f-8e5a3d15640e`。未发送密钥或无关文件。其对保存、未来版本、缓存竞态、关窗的判断有本地反例支持。

不采信其两项未证实推断：geometry.stop 实际清空 pending 并等待结束，不能说必然继续排队；MergeRunner FailedToStart 后 is_running 读 QProcess 状态，不能说永久 busy。错误分支未完整关闭日志/清队列/发 allFinished 值得继续测试，但没有足够反例时不升格为已确认。DeepSeek 不决定物理口径。

## GUI 全链路检查边界及待办（历史初次记录）

已检查数据发现 → ROOT/CSV loader → build_plot → PlotPanel 曲线/色条 → CSV/PNG 导出，以及 ScanPage 计数缩放 → 绘图/导出、i18n。配置、runner 成功判定、场景计算未改。

方法待议（未顺手修改）：现有 mesh_profile/map 以 cell errors 平方和开根号作投影误差，代码假设 cell 独立；同历史跨多个 cell 可有协方差。LET ratio 也被既有通用 per-event 选项除以事件数，其物理意义应由科学方法审查明确，不能在 R-05 名称修复中偷偷改变数值。

文档交主代理：同步 GUI AGENTS C1 的旧“每初级粒子”表述、输出契约中 CSV 附加列与扫描导出语义、ROOT 缺 metadata 必须显式 n_events 的迁移说明及弃用 API。未宣称 GUI 全仓库审查完成。
