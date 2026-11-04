# J3 收尾组 6 准备报告（冻结身份 / 正式矩阵复用 / 提交与 CI 最短步骤）

日期：2026-11-04（Asia/Shanghai）
执行：DeepSeek 执行负责人（本轮受命只读准备）
结果：**准备完成，未执行任何变更**——未提交、未推送、未启动测试、未装依赖、未占桌面、未改产品/测试/CI。

## 1. 交付物

| 路径 | 内容 |
| --- | --- |
| `out/collab/j3-closeout-release/candidate-identity.json` | 机器可读冻结身份（生成脚本同目录 `build_identity.py`）：HEAD/分支/远端/跟踪状态、8 候选文件 sha256 与字节数、worktree 未跟踪快照、exe/merge 指纹 |
| `out/collab/j3-closeout-release/README.md` | 一句话结论与索引 |
| `out/collab/j3-closeout-release/reuse-map.md` | 既有正式证据逐项“可复用/须补测”判断与 backend 字节映射依据 |
| `out/collab/j3-closeout-release/formal-matrix.md` | 干净 worktree 冻结、static/gui/integration 正式矩阵命令、判定、时间预算、证据归档 |
| `out/collab/j3-closeout-release/freeze-commit-ci.md` | 冻结→提交→推送→CI 触发与校验→失败处理→回退 |
| `out/collab/j3-closeout-release/risks-and-questions.md` | 13 项风险与 9 个待主审拍板问题 |
| `out/collab/j3-closeout-release/release-commands.sh` | 可复制命令（默认 print，`J3_RELEASE_GO=1 … execute` 才执行） |

本轮**没有**修改仓库内任何被跟踪文件；`out/` 本身被 `.gitignore` 忽略，故以上文件也都在被忽略目录内。

## 2. 候选范围与身份（已核对）

- 分支 `roadmap/gui-theme-response`，HEAD `0368abceb95469350e1408cc67a36f17fff0c5f7`；
  **未配置 upstream**；远端跟踪 ref `origin/roadmap/gui-theme-response` 当前等于 HEAD；
  显式推送命令 `git push origin HEAD:roadmap/gui-theme-response`。
- `origin/HEAD -> origin/codex`；本地领先 `origin/codex` 35 提交、落后 0；`credential.helper=manager`；本机无 `gh`。
- 候选 8 文件（7 修改 + 1 新增，diff +338/−21），sha256：
  - `.github/workflows/linux-geant4.yml` `8c4e7089…`
  - `.github/workflows/m0-static-gui.yml` `848ed5c9…`
  - `gui/g4usim_gui/core/fonts.py` `78432cc6…`
  - `gui/g4usim_gui/preview3d/pyvista_preview_widget.py` `d7a9dcff…`
  - `gui/g4usim_gui/window/workspace_layout.py` `da297463…`
  - `gui/smoke_tests/smoke_workspace_layout.py` `1b91a27f…`
  - `gui/smoke_tests/smoke_vtk_axes_theme.py` `22030597…`（新增，14953 B）
  - `scripts/run_m0_tests.py` `3d745f56…`
- 其余 61 项未跟踪属于用户交接材料（`docs/collab/**` 51、`docs/verification/independent-*-20261029` 7 个目录、
  `tools/collab/`、根目录 Astra 交接 md），**不得**纳入提交。

## 3. 正式测试复用结论

- **E1**（`docs/verification/j3-status-contrast-20261103/`：head `c082eccc`、dirty=false、static 49/5687、
  gui 76/10535、integration 33/6830）**不可复用**：GUI 产品、GUI 测试树与 runner 均已变化，
  `tests_content_fingerprint` 不同；仅作数字基线。
- **backend**（`docs/verification/j2-f8-final-20261102/tree/…/j2-f8-18c5858/windows113-backend/20261102-040211-305d428b/report.json`：
  head `18c5858f`、dirty=false、63/82029、source `9e40e889…`）**可按产品字节映射复用**：
  `18c5858f..HEAD` 在 `src/`、`include/`、`main.cc`、`CMakeLists.txt`、`cmake/`、`test/`、`config/`、
  `scenarios/`、`schema/` 全无变化；`scripts/` 仅 runner +20 行与新增 static 用例；backend 用例脚本与断言未动。
  复用需接受两点显式偏差：`git_head` 是 `18c5858f` 而非 C1、`tests_content_fingerprint` 基于旧 GUI 测试树——
  证据 README 与最终报告必须写明，不得冒充候选运行。备选重跑 backend 需先重建 mergeHistograms（见风险 R3），约 32–45 分钟。
- static / gui / integration **必须**在候选提交 C1 上重跑；仅在干净 worktree 中跑（主工作区 62 项未跟踪会让
  `git_dirty=true`、`tracked_source_gate=fail`）。

## 4. 最短可执行步骤（细节见 formal-matrix.md / freeze-commit-ci.md）

1. 提交 C1：只 `git add` 8 个候选路径；commit message 建议
   `feat(gui): restore analysis page constraints and theme-readable VTK captions`。
2. 冻结：`git -c core.longpaths=true worktree add --detach <TEMP>/g4j3-final/G4UniversalSim C1`；
   确认 `git status --porcelain` 为空；复制 `gui_runs/`（780 KB，夹具，`.gitignore` 忽略）。
3. 矩阵：干净 worktree 内逐层跑 static（49 例）/ gui（77 例）/ integration（33 例），
   `--require-tracked-sources --fail-on-skip`，每层过 `check_report_evidence.py`；
   static 前 `PATH=/d/msys64/ucrt64/bin:$PATH`（10 个 cxx 用例）；integration 传
   `--executable …G4UniversalSim.exe`（sha256 `18d58fab…`，与当前源码指纹一致）与 `--merge-executable`。
   预计 25–33 分钟；报告须 `git_head=C1`、`git_dirty=false`、`tracked_source_gate=pass`、`skip=0`。
4. 证据：复制三层 `report.json`+`logs/` 到 `docs/verification/j3-final-20261104/`，写 README（含 backend 复用标注、门禁输出、复现命令、不证明什么）；提交 C2（证据 + 本报告 + STATUS/ROADMAP/CHANGELOG/AGENTS/agent-history/测试平台说明）。
5. 推送：`git push origin HEAD:roadmap/gui-theme-response`（无 upstream，不可省略 refspec；不 force）。
6. CI：两条 workflow 均 `on: push` 自动触发——M0（ubuntu/windows 各 static+gui）与 Linux（Geant4 11.3.2/11.4.3 各 static/gui/backend/integration+门禁+篡改对照），产物 `m0-report-*`、`linux-evidence-*`；
   历史双绿基线为 `45891c3` 的 M0 run `40680571889`/`40680563877` 与 Linux run `40680571833`/`40680563958`，**本候选必须重新真跑**。
   本机无 `gh`：用 Actions 页面与公共注解核对（job 日志需登录，主审可复核），记录 run id 与 artifact。
7. 失败处理：只对候选缺陷做最小修复并以新 commit 推送；环境/基础设施失败用 Re-run failed jobs；不改门禁、不 force-push。

## 5. 需主审拍板（详见 risks-and-questions.md §2）

1. backend 复用 A（推荐）/ 重跑 B；
2. 单提交 C1（推荐）/ 拆两个提交；
3. 只推特性分支（推荐）/ 同时快进 `codex` 或开 PR（无 gh CLI，网页操作）；
4. C2 文档范围：证据+outbox+STATUS/ROADMAP/CHANGELOG/AGENTS/agent-history/测试平台说明（推荐）；
5. 是否重建 mergeHistograms（组 6 不需要，走 backend 重跑才需要）；
6. 3D 依赖钉版本建议留作后续任务（本候选不扩范围）。

## 6. 本轮未做与未验证

- 未提交、未推送、未启动正式矩阵、未跑任何测试、未触发云 CI、未安装依赖、未操作桌面；
- CI 实际时长、3D wheel 下载体积、推送凭据的本轮可用性未验证（仅核对到远端跟踪 ref 已等于当前 HEAD）；
- 所有“期望”数字来自既有报告与只读核对，不代表候选已通过；正式结论以 C1 上的实际报告与云 CI 为准。
