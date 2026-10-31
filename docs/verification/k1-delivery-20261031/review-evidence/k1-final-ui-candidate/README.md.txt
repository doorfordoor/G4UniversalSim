# K1 最终UI修复候选（仅OUT）

基线 `f9a9ddbfcabe69067707a5a209caff005748f510`。本目录为唯一写入范围，四产品+两既有smoke替换源均由本写者独占。正式第五Windows会话未查询/未干预；未修改tracked、未提交、未跑完整矩阵。用户给定模型6.1Sol/high，usage unknown；独立审查待父任务/Averroes，不自行签署。

## 两个修前反例已先留存

先在原产品字节上运行，再写产品修复：

- `baseline-cwd.log` exit1：确实到“actual completed record cwd absent from preview”断言，不是fixture/setup错误。输入来自8213ced原生末轮真实完成record `880d4e7eb8e0481da3cf0c2d380bafbc` 和保存项目，实际执行目录与编辑目录不同。`source-record-evidence.json`绑定原state/项目/磁盘record SHA，且核对record_id/status/command/launch/execution_bundle与持久化原record一致。此过程只重放显示，不重跑模拟。
- `baseline-pending.log` exit1：用现有 `ExperimentWorkflow._state()` 生成真实producer字段，fields=passed+qualification=checking被投影为pending；旧面板确实显示Unobserved。不是构造消费者自己定义的期望键。

`baseline-*-observation.json` 与 `baseline-results.json` 保存原显示、payload、退出码、日志SHA。原件不改写成绿。

## 最小产品变化

1. `window/run.py`：formatter只加两个可选显示参数。未传参数时，动作前旧预览全部字段/顺序/文本保持；显式传入执行cwd时显示“逻辑工作目录”。进程创建cwd不同时另列“进程启动目录”。空command仍为空，不改编辑项目。
2. `window/experiment.py`：记录存在actual launch时，预览取其observed program/arguments、logical cwd与launch cwd，避免restore路由的transport参数丢失。Generate尚无进程收据时，取execution_bundle.path作为逻辑执行目录；两者都缺失则显示Unknown，不能借编辑cwd伪造观测。F5原有config/macro/output显示绑定保持，不增加workspaceRoot回写，不改变资格/历史/持久化/进程所有者。
3. `widgets/experiment_panel.py`：仅补producer实际使用的pending→In progress；未知值仍回退Unobserved，历史原passed事实不被改写为新通过。
4. `core/i18n.py`：集中加入两个cwd标签及In progress→进行中。没有第二controller、core/runner修复或资源规则变化。

## 有意义的既有测试增补

- `smoke_k1_workflow.py`：保留原39个assert AST，增加到57站点。完整旧pre-dispatch列表相等；真正completed Generate使用execution cwd；分别用现有launch planner生成direct/restore收据渲染actual argv和两类cwd；中英文标签；缺失事实为Unknown；project.workspaceRoot、pathSettings.workspace_root、路径控件、F5捕获快照指纹以及原record均保持。planner收据为明确的受控显示输入，Python/Geant4不会被这些planner fixture启动，不假称真实模拟。
- `smoke_k1_panel.py`：保留原67个assert AST，增加到74站点。实际producer分别生成后台重验和新执行pending。预期固定为英文In progress/中文进行中，不从STATUS_TEXT计算；检查summary/level/history以及物理层未观测、payload不变。原未知值回退、四层独立、busy/cancel、语言和布局断言全部保留。

## 窄验证终态

| 检查 | 退出码 | v3入口 |
|---|---:|---:|
| 原产品+真实完成记录cwd反例 | 1（保留红例） | 2 |
| 原产品+producer pending反例 | 1（保留红例） | 2 |
| 候选+同一真实cwd记录 | 0 | 3 |
| 候选+同一producer pending | 0 | 2 |
| 增强K1 panel整脚本 | 0 | 1629 |
| 增强K1 workflow整脚本 | 0 | 80 |

六源语法编译通过；原assert AST多重集合无删除；`git apply --check candidate.patch`通过。候选绿日志没有Traceback。所有编译/临时输出在本目录，仓库原v3探针未改。仅OUT内存overlay，__file__保留正式位置用于fixture定位，编译文件名指向候选以正常计数。

这不是独立审查、完整矩阵、实窗重新观察或物理验证；父正在运行的第五formal不被这些候选替换。

## 交付及真实SHA

完整替换源：`files/`；原件字节：`baseline/`；补丁：`candidate.patch`；每文件原/候选SHA、原始日志SHA、退出收据与来源：`manifest.json`。补丁 SHA256：`6e7c23632dd46b7123bfebde736e627e0f41a2a2a28af53ccc5796caef94c0a0`。

| 文件 | 候选SHA256 |
|---|---|
| `gui/g4usim_gui/window/run.py` | `3af4daefa4c0818fba9879acffe14e15ece2c8b908d2b26b0526e9fa7e873d56` |
| `gui/g4usim_gui/window/experiment.py` | `2cb03d1ad4d83fb5ae0608ddb79e82976e1df0c742aabdd1819e0766de224258` |
| `gui/g4usim_gui/widgets/experiment_panel.py` | `01f91f3db0081536110e2acc9958ec76783af485dbbc1f378ec52231f94133f3` |
| `gui/g4usim_gui/core/i18n.py` | `002de76b33480160415c3c4b2fb9e38455b2ce94b1aedacfcd83121387ecdf0a` |
| `gui/smoke_tests/smoke_k1_workflow.py` | `05ff02dae6a38375ecb5e39f3f79a33a80cef29318fa003f41aec4c94f3f5968` |
| `gui/smoke_tests/smoke_k1_panel.py` | `658fcb292ca0b2ab60b8ef73bd3a4d285593c13824076850e4bd8cfbef8d38a0` |

## 独立复核入口

所有既有日志已保存，可先只读检查 `manifest.json`、两个observation和真实来源收据。需要重放时请在独立OUT复制目录保留原证据后运行，不覆盖本轮原日志/observation：

```powershell
python -B out/collab/k1-final-ui-candidate/run_candidate.py reproduce --baseline --case cwd
python -B out/collab/k1-final-ui-candidate/run_candidate.py reproduce --baseline --case pending
python -B out/collab/k1-final-ui-candidate/run_candidate.py reproduce --case cwd
python -B out/collab/k1-final-ui-candidate/run_candidate.py reproduce --case pending
python -B out/collab/k1-final-ui-candidate/run_candidate.py smoke_k1_panel.py
python -B out/collab/k1-final-ui-candidate/run_candidate.py smoke_k1_workflow.py
```

第四前端独立review `k1-final-frontend-independent.md/json`仍是8213ced/f9相同前端字节的历史两发现，不改写为候选已通过，不修改第四覆盖图。候选是否接收/集成及第五正式矩阵由父与独立审查者决定。已拒资源边界/late-reparse不在本任务，未重试/换名执行。
