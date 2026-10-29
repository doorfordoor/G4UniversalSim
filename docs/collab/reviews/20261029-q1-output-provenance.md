# R27 自动目录后处理来源契约

工作区 effective-config，原 D 盘只读。修复前用当前 Python 读取旧审查归档，reused_output 的 raw Edep=2.1 MeV、current_files_only=0.1 MeV，均无警告。证据 `out/q1-output-provenance/before.json`。不重新启动后端冒充旧反例。

## 完整提案 / 验收

1. 新建无 Qt `gui/g4usim_gui/output/provenance.py`。目录存在 run_metadata.json 时必须为 run_metadata_json_v1，generated_files 为合法且不重复的 path/schema 记录，所有登记文件存在；任何损坏/缺失登记文件令整个自动集合失败，不能对剩余文件继续成功。对文件名 run 后缀与 runs ID 校验。仅读取白名单，不删除/重命名未登记文件。
2. 可移植副本：后端记录的是原始绝对路径，以 manifest 自身登记 path 的父目录作为原 output 根，要求全部登记文件属于该根；映射为当前目录中的相对路径，不访问原机器路径。拒绝逃逸、重复、混杂根及歧义，不仅按 basename 猜映射。相对路径只允许目录内规范路径。
3. 缺 metadata 的旧目录保留读取兼容，但统一明确标记 legacy/unverified。reader 返回 warnings，绘图 notes、GUI 来源提示、JSON provenance 标明，CLI 自动扫描向 stderr 警告；不称“当前成功”。显式文件/文件清单不强行绑定邻接目录 manifest，保持离线分析 API。
4. Dose/Fluence、JSON、pulse/event、scorer/mesh/hist/phase plot、merge 计划与 CSV CLI 共用 helper。绘图加载再次校验，避免旧 DataSet 选择绕过新发现结果。merge 使用经过校验的显式文件清单交给原工具，不能再传目录 glob 使执行器重新混入陈旧文件。缺文件/manifest错误在 GUI 显示错误且不生成可执行计划。
5. 文件浏览器可展示包配置/日志和未登记文件，不能把展示当统计输入；统计自动消费者必须走 helper。继续盘点 ROOT 对比、场景、轨迹等公开目录入口；专用明确列表 API 不破坏。元数据仅证明来源登记与存在，不证明文件字节未被外部篡改或物理正确。
6. 正式回归：旧快照修复前后、当前1/2 worker及多run、2worker→1worker与2run→1run复用、旧文件注入、复制迁移、缺登记文件/JSON损坏/schema/重复/逃逸、无metadata legacy、显式文件兼容、GUI和JSON一致、pulse N、merge排除陈旧文件。新增 `scripts/test_output_provenance.py` 与必要 GUI smoke，runner case 由主负责人登记；C++/main/共享契约不改。

## 进度

实现完成，Python 文件冻结；未改 C++/main/共享 runner/输出契约。当前来源登记仅证明所选文件属于 manifest 清单，不代表运行成功、字节真实性或物理验证。

补充必需项：无论绝对路径还是相对路径，manifest 必须恰好登记当前目录的 run_metadata.json 与 run_summary.txt；空清单、遗漏两者任一均拒绝。绝对路径仍按自身登记锚点迁移。重复 canonical 路径拒绝，所有登记文件必须存在。真实后端专项验证此约束与正常输出相容。

### 改动清单

- 共享 helper：gui/g4usim_gui/output/provenance.py。
- GUI 自动输入：output/{dose_summary,fluence_summary,plot_data,merge_plan,merge_runner}.py；widgets/{output_page,plot_panel}.py；core/scan.py；preview3d/trajectories.py；window/content.py。
- 脚本：scripts/extensions/{dose_json_extension,fluence_json_extension}.py；scripts/{merge_outputs,compare_root_csv,run_benchmarks}.py。
- 场景自动分析：scenarios/detector_response/analyze_detector.py、semiconductor/analyze_device.py、shielding_coating/analyze.py。缺失登记文件保留 shielding CLI exit 3 证据错误语义。
- 新测试：scripts/test_output_provenance.py（无参数 synthetic，--backend 实际后端）、gui/smoke_tests/smoke_output_provenance.py。
- 兼容 fixture：gui/smoke_tests/{smoke_dose_results,smoke_fluence_results,smoke_plots,smoke_start_page}.py；scripts/test_q1_postprocessing.py。

### 验证证据

旧只读归档修复后 reused_output Edep 从 2.1 回到 0.1 MeV，Dose=2.0027207925e-12、Fluence=1.87513895905e-05，pulse N=1，merge 只选择本轮 t0。out/q1-output-provenance/{before,after}.json 及 after-dose_json.json/after-fluence_json.json 保存前后证据；未改 D 盘归档。

新 synthetic 与 GUI 专项通过，覆盖 stale worker/run、相对/绝对 manifest、复制、空清单/必需项缺失、损坏、缺登记文件、显式列表兼容及 JSON CLI 不发布错误结果。backend 专项 1/2 worker、多 run、复用输出目录后退到单 worker/单 run 与可移植副本全部通过；最终日志 out/q1-provenance-backend-final.log。使用 clean 4e6fa7a 的 out/build-q1-clean/Release/G4UniversalSim.exe，SHA256=97590cf8eafb2f42c36bcd526b84ff6b0e29569432ef477240d7d025038fb75a；此证据仅验证当前 Python 与该已有二进制，不替代正在修改的 C++ 最终验收。

完整 GUI profile：out/verification/q1-provenance-gui2/20261029-161531-bb60df4f/report.json，30 PASS、0 FAIL/SKIP、2128 assertions。此报告产生后补了必需登记检查及 shielding 错误兼容；随后新 synthetic/GUI/backend 专项均再次通过，最终全套由主负责人统一执行。之前 gui profile 的 2 FAIL 已保留作定位记录，不当最终通过证据。

场景实际回归 test_scenario_shielding_core 与 test_shielding_coating 均通过；out/q1-provenance-scenario2.log、out/q1-provenance-shielding.log。轨迹 loader/settings 通过，但独立 trajectory widget/backend 缺依赖时跳过，不扩大声称。

### 兼容性变化与边界

内置 energy_scan 归档仅保留部分结果，其 manifest 登记的 Dose 文件缺失。自动扫描现在明确 incomplete/no metric，不能把裁剪归档冒充完整输出；测试用显式 scorer_statistics 单文件继续检查原数值趋势。未改归档、未伪造完整清单。缺 metadata 目录继续 legacy/unverified 兼容且提示；显式单文件与显式清单分析保持可用。文件浏览器仍可展示未登记日志/配置，不能将其作为自动数值输入。

建议 runner case：output_provenance（static，无后端）、output_provenance_backend（integration，参数 --backend，依赖 G4USIM_EXE 与 Geant4 数据）、gui_output_provenance（GUI）。测试临时目录自动清理，无常驻 GUI 或后台模拟进程。

## 独立补查：原生mergeHistograms目录入口

root发现tools/mergeHistograms.cc:127的自动--input目录模式仍绕过manifest。提案：原生工具保持无JSON/Python依赖，目录有metadata时明确拒绝未经验证的glob并指导GUI（统一manifest helper）或显式文件清单；无metadata目录继续兼容但输出legacy/unverified警告。显式文件模式保持。验收：有manifest/损坏manifest自动模式均失败且不写新合并文件，显式清单仍可分析，legacy提示；在histogram_merge专项中登记。不是静默忽略manifest，也不删除旧数据。

## R27 独立 ROOT 借数补修提案

显式 ROOT API 当前会从相邻 metadata 借事件数而未核对文件登记，真实 uproot 反例：未登记的2事件 ROOT 被新目录100事件 metadata 解释为 N=100。仅修改 scripts/g4usim_io.py 与 scripts/test_q1_postprocessing.py，复用共享 provenance.py：合法登记且 run 匹配才自动取 N；未登记文件无显式 N 拒绝，有显式 N 保持独立分析；损坏 manifest 一律拒绝，不能伪装 legacy。无 metadata 仍需显式 N。验收覆盖 scorer/mesh、复制目录、run 不匹配、坏 manifest 和显式 N 冲突；不运行后端。原始反例复制保留于 out/verification/r27-root-metadata-before。

补修完成并冻结：g4usim_io 的事件数与 mesh bins 均复用 output_evidence，未登记文件不借相邻参数，损坏 manifest 拒绝；事件数只有标准 ROOT 文件名与已登记 run 对应时自动取值。显式 N 保持离线分析；registered metadata 与显式 N 冲突仍拒绝。正式真实 uproot 回归包括未登记2事件 ROOT/100事件 metadata、scorer/mesh 两入口、显式 N、复制绝对路径 manifest、run 缺失与损坏 manifest。test_q1_postprocessing exit0/v3 asserts123，test_output_provenance exit0/v3 asserts46。日志 out/verification/r27-root-metadata-after.log、r27-root-provenance-regression.log；原始反例目录 out/verification/r27-root-metadata-before。未运行后端或构建，两个 Python 文件冻结供主负责人整体验收。

## DeepSeek R27 独立审阅与本地核对

沿既有API流程，provider https://api.deepseek.com/chat/completions，请求/实际返回模型 deepseek-flash；response ID 8f6ab114-c26b-4c99-9078-2c3139317a84。输入仅provenance helper全文及Dose/Fluence、plot、merge、OutputPage/PlotPanel、两种JSON扩展的当前diff和R27契约；未提交无关源码或密钥。未运行后端、未改源码。原始机器回复 out/collab/q1-r27-independent-review.json。

### 原始回复（原样保留）

# R27 残余缺陷审查

## 确认（有路径支持）

1. **plot stale selection 未覆盖 `_on_dataset_changed` 失败回退。** `plot_panel.py` 只在 `discover()` 抛错时清空 `_datasets` 并显示 `discovery_error`；但目录切换后若 `discover()` 成功、而用户选中的 dataset 依赖的 per-dataset 文件在 manifest 里被 `require` 拒绝（如 `plot_data.scorer_plot`/`load_mesh` 的 `require`），异常路径未在 `set_output_dir` 处兜底。`_update_buttons`/`_on_dataset_changed` 未在 diff 中出现，无法确认其捕获 `ProvenanceError`；但 `discover()` 成功即可视作现行假设下唯一进入组合框的通道，说明 dataset 级 `require` 失败没有对应的 UI 失败状态文案（可能只上抛）。→ 待验证：需要 `_on_dataset_changed`/`scorer_plot` 调用的包装是否吞异常。

2. **merge 再校验仅比对文件列表，不比对文件内容/元数据一致性。** `merge_runner.py` 用 `output_files(...)` 重算，但 `output_files` 对 legacy 目录返回 glob 全集（无 metadata 时 `matching()` 仅按名过滤，`run_metadata.json` 缺失下不 reject），且不校验 manifest mtime/hash。计划期有 manifest、执行期 metadata 被删除 → `output_files` 落回 legacy，若文件名集合相同则"未变化"通过，违反"存在 run_metadata 时只用 generated_files"的强约束在**执行时**已被绕过。→ 确认：路径在 `merge_runner.py` 的 `output_files` + `provenance.output_evidence` 的 legacy 分支组合；需在 runner 侧显式区分"计划时是否有 document"。

3. **merge 再校验丢弃了 `matched_files` 的顺序语义。** `MergeTask.matched_files` 是 `sorted(str(path))`（`merge_plan.py` 中 `evidence.matching` 返回 sorted），runner 侧 `current` 也是 sorted，一致；但 **args 已改为 `["--output", out, *matched]` 位置参数**，把"自动扫描的目录"变成"显式文件清单"。这与既有 `--input DIR --pattern PAT` 契约不是同一后端契约：若某后端脚本仍以 `--input`/`--pattern` 实现而忽略位置参数，`automatic_inputs` 路径的 `args` 构造（merge_plan.py 第 `args = [... *matched]` 行）会把自动发现误降为"显式清单兼容"，与题述"显式文件清单保持兼容"方向相反地**改变了自动目录的调用契约**。→ 待验证：需确认后端脚本支持位置参数；仅 diff 无法判断。

4. **`pulse_plot` 的 `next(...)` 在无该 run 时抛 `StopIteration` 未转为 `ProvenanceError`。** `plot_data.py` 第 335 行 `next(r for r in evidence.document["runs"] if r["run_id"] == dataset.run_id)` 无默认值；`metadata_values`/`run_events` 处使用了 `next(..., None)`。若 `discover()` 从某文件推出 run_id，但 manifest `runs` 未记录该 run（`output_evidence` 只校验"文件引用的 run 存在"，不校验 dataset 推导的 run_id 一定在 runs 中——实际上两者一致，因为文件级校验 `run_id not in run_ids` 会失败），则此处多此一举且引入不一致。→ 确认：diff 内该行确实无默认值，属健壮性缺口；触发条件需 `discover` 能从文件推出不在 `runs` 的 run_id，与 `output_evidence` 的 run 存在校验冲突，故**实际不可达**——归类为待验证（需构造绕过文件级校验的路径）。

5. **`run_events` 在有 metadata 时仍返回 `None` 或 manifest 值，但 `build_plot` 的 per_event 归一路径（`plot_data.py` 第 424 行附近）只加 run_summary 说明文案，未在 `events is None` 时拒绝。** 若 manifest document 存在但 `run_id` 不在 `runs` 中，`next(..., None)` 返回 `None`，后续 `plot.value /= events` 路径（未在 diff 中）可能除零或跳过归一——需确认此分支。→ 待验证。

6. **GUI/JSON 失败状态不对齐：** `dose_json_extension.process` 与 `fluence_json_extension.process` 在 `read_*_summaries` 抛 `ValueError`（含 `ProvenanceError`）时**不**转为结构化失败输出，而是让异常冒泡；`output_page._update_dose_summary` 却把同样的 `ValueError` 转成 `records, warnings = [], [str(error)]`。即 JSON 扩展与 GUI 对同一 provenance 拒绝的呈现路径不同（异常 vs warnings 列表）。→ 确认：`dose_json_extension.py` diff 只在成功返回里加了 `provenance` 字段，无 try/except；`output_page.py` 有。两者失败模式不一致。

7. **`output_page._update_run_summary` 在 `run_summary.txt` 未登记时用硬编码英文文案，与 `_update_dose_summary` 的 `str(error)` 风格不一致，且未提示 `evidence.warnings`（metadata 缺省场景 warning 未显示）。** 此外 `path and Path(path) not in evidence.files` 判定：legacy 下 `evidence.files` 是 glob 结果，`Path(path)` 应为同一路径，成立；但 `_find_first` 返回的 `path` 类型未在 diff 中确认，需确认其为 `str` 且与 `evidence.files` 的 `Path` 可比较（`Path in tuple[Path]` 支持）。→ 待验证：`_find_first` 返回类型。

## 待验证（需 diff 外代码）

- `_on_dataset_changed` 与 `scorer_plot`/`load_mesh` 调用点是否捕获 `ProvenanceError`，决定缺陷 1 是否真实存在。
- merge 后端脚本是否接受位置参数文件清单，决定缺陷 3 是否为契约破坏。
- `build_plot` 在 `run_events` 返回 `None` 且 `document is not None` 时的除零/跳过行为。
- `output_page._find_first` 返回类型与 `evidence.files` 元素类型是否一致（缺陷 7）。

### 本地逐项核对

1. 撤回“绘图错误上抛”判断：plot_panel.redraw先清figure/_plot，try内包括_sources与build_plot，except显示错误并更新按钮；_on_dataset_changed最终调用redraw。dataset文件失效不会保留旧数值为新成功。
2. 确认有限范围竞态：MergeRunner只比较文件列表，计划有manifest、启动前删除manifest且匹配列表不变时，校验可降级为legacy而通过。无Qt最小反例已得到automatic_inputs=true、same_inputs_after_manifest_deletion=true；out/collab/q1-r27-merge-downgrade.json，仅比较守卫输入，未启动任何合并进程。legacy RuntimeWarning存在，但不会通过errorOccurred显式阻止旧计划。建议计划保存provenance模式并在启动前要求一致，降级提示刷新；不要求哈希所有文件、不扩大为真实性保证。源文件冻结，本次只报告未修。
3. 撤回位置参数不兼容推断：merge_outputs argparse files nargs=*；mergeHistograms ParseArgs明确接收位置文件并有usage示例，当前构造有后端支持。
4. 不升格：normal discovery的文件run已由helper验证；stale DataSet无匹配run可能出现StopIteration，但redraw捕获所有Exception，属于错误信息质量边界，未证明错误数据成功发布。
5. 撤回：plot_data.build_plot明确events is None or <=0即ValueError，不能跳过归一化或除零成功。
6. 撤回“失败状态不对齐”缺陷判断：JSON入口run_output_extension捕获ValueError并stderr/非零，正式专项验证不发布文件；GUI清表并显示错误。不同呈现适应CLI/GUI入口，不等于成功语义冲突。
7. 撤回legacy警告缺失判断：_update_run_summary在574–575显式prepend provenance与evidence.warnings；Path比较也是Path与Path。英文原始错误文案为呈现质量事项，未形成新的结果误判。

结论：7项建议仅第2项确认待修，另第4项为可捕获的stale-selection文案边界；其余经完整调用链核对撤回。本次并非DeepSeek桌面视觉或真实后端验收。

### 合并来源竞态修复提案（实施前）

响应8f6ab114-c26b-4c99-9078-2c3139317a84确认项2：OutputEvidence记录与解析同一次读取的manifest字节SHA256，自动MergeTask存来源模式及摘要；启动重读校验模式、摘要及文件列表，任一变化拒绝并要求刷新。legacy计划继续明确未验证，显式清单automatic_inputs=false保持兼容。这仅绑定计划和来源清单快照，不证明数据内容未变，不承诺跨进程原子快照。GUI smoke覆盖删除manifest同文件名、变更run身份同文件名、不变计划可启动。

合并来源竞态候选完成并冻结：helper的manifest_digest由同一次read_bytes解析并SHA256，不二次读取混身份；MergeTask存provenance_status/manifest_digest，runner执行前重新校验并比较模式/摘要/文件列表。修改仅provenance.py、merge_plan.py、merge_runner.py、smoke_output_provenance.py。

smoke_output_provenance通过：删除manifest同文件名、合法manifest新增run身份但同文件名均不调用启动；不变manifest正常到达启动；legacy计划明确Legacy/unverified且可启动；显式清单可独立于manifest启动。启动观察使用替换QProcess的StartProbe，执行真实MergeRunner守卫、信号与参数流程但不创建子进程，不冒充真实merge或Windows窗口验收。test_output_provenance再次通过；定向diff check通过。未启动后端、未改其它源码，供主负责人统一验收。

## R26/R27/R30 二次独立只读审查

最终候选范围未发现新的确认阻断缺陷。本次仅源码与既有记录复核，未修改产品/测试源码、未重跑已通过测试。

- R27：provenance.py:55–126解析和摘要使用同一份读取字节，必需登记、缺文件、路径逃逸和重复检查保留；merge_runner.py:69–84启动前比较模式/摘要/文件列表，变化清队列、报错并要求刷新。manifest摘要仅绑定来源清单快照，不保证数据内容真实性或跨进程原子快照。
- GUI/JSON：output_page.py:462、490、559清表/展示来源错误，legacy警告可见；JSON入口非零拒绝、不发布错误结果。registered_manifest不替代run_result运行成功或物理判定。
- R30：main.cc:777、816、979自动bias初始化仅首次；已有run后batch/csh在执行前拒绝四类重建命令，保留宏失败位置或run_lifecycle分类。核对geometry审查中build6 26/26实测及test_run_reinitialization.py断言，包含真实run ID、首轮文件保留与后续命令未执行，不仅退出码。该26/26为既有实测证据，本次未重复运行。
- R26：main.cc:118、972–999 alias展开及斜杠规范化后守卫/执行使用相同命令；条件派发拒绝、CLI锁及restore先独立校验后commit/rollback链保持。

本结论不扩大到Qt原生交互会话任意命令或完整生命周期审计。

### 最终Windows实窗准备

已只读检查gui/smoke_tests/smoke_q1_windows.py：必须win32且QT_QPA_PLATFORM=windows，G4USIM_EXE指定最终binary，输出根为该脚本所在工作区out/q1-gui-review/时间戳；保存→生成→20事件成功→独立目录取消→再启动关窗，检查所有所属QProcess停止。report含exe SHA、输出身份、summary SHA及运行/取消/关闭结果；截图results.png、cancelled.png、before-close.png。等待主负责人明确最终干净worktree与exe后才执行，不运行旧binary、不修改脚本；完成后必须用image工具打开results/cancelled截图进行真实查看，不能仅以路径宣称视觉验收。

## 提交前 static 夹具兼容修正

static-precommit报告20261029-174906-ca3b655a的两项失败均为旧测试假设：platform_paths发现provenance fixture写死盘符，改为实际临时目录绝对路径（仍测复制锚点，不规避扫描规则）；shielding_analysis的mock manifest缺自身metadata/summary登记，补完整登记。负向helper同时接受新共享ProvenanceError并核对原错误文本。旧mixed-run夹具仅创建未登记后续run文件，新契约应忽略：现明确验证未登记文件不参与，再登记该r1文件、验证缺run1的manifest被严格拒绝。不改产品/runner/probe。仅重跑两失败case：platform_paths exit0/v3 asserts3；shielding_analysis exit0/v3 asserts113。日志out/verification/r27-static-platform-paths.log及r27-static-shielding-analysis.log。两个测试与本记录冻结。
