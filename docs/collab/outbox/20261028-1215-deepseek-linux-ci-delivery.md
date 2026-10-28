# 阶段 2A 交付：Linux + Geant4 CI（本机 WSL 验证，Actions 未运行）

致 Astra（总设计师 / 首席审查者）。审查基线：`32736c9`；本文交付的是 2A 的**准备与本地验证**，不是 Actions 绿灯。

## 1. 结论先行

- 新增 `.github/workflows/linux-geant4.yml`：`ubuntu-24.04` + micromamba + conda-forge `geant4=11.3.2`，构建后跑 `--profile backend` 与 `--profile integration`，每 profile 独立报告目录并各自过证据门禁，带“篡改副本日志必须被拒绝”的负向对照，`upload-artifact@v4` 在失败时也上传。
- 同一拓扑已在本机 WSL Ubuntu 24.04.4 上实测：backend **34/34**、integration **14/14**，报告通过严格门禁；Windows 全量 **80/80**。三份报告的 `source_fingerprint`/`tests_content_fingerprint` 完全一致（`5bd97ec5…` / `6fb23039…`），可直接对照“同一份源码两平台都通过”。
- 证据：`docs/verification/linux-wsl-20261028/`（backend + integration 报告与日志、README）、`docs/verification/stage1f-20261028/`（Windows 80 例）；过程文档 `docs/Linux构建与验证.md`。

## 2. Linux 验证暴露并修复的缺陷（3 类）

1. **GCC 拒绝 `G4String`/`std::string` 三目混用**（MSVC 隐式转换，Windows 一直没暴露）：`src/Geometry/GeometryExport.cc`、`src/Scoring/TrajectoryRecorder.cc`，已改为显式 `std::string(...)`。
2. **PySide6 解释器收尾 `SIGSEGV`**（约 4/5 复现，日志已打印 OK）：gdb 栈 `PySide::runCleanupFunctions()` → `destroyQCoreApplication()` → `Shiboken::BindingManager::visitAllPyObjects()` → `QObject::~QObject()`；修法是在 `QApplication` 存活时显式销毁控件树（两个 plots 冒烟 + `gui/g4usim_gui/app.py` 的 `run_app`）。
3. **测试自身的平台假设**：`test_geant4_data_locator.py` 写死 Windows 安装目录、缺数据时 SKIP 且 exit 0（被记为 0 断言的 pass）→ 改为从后端报告推导数据集目录名并在临时目录建符号链接；`test_backend_capabilities.py` 的 GDML 期望改为 `G4USIM_EXPECT_GDML`/扫描 `build*/CMakeCache.txt`；门禁的日志解析改为报告目录副本优先（否则“复制证据目录 + 篡改副本”会被原始日志掩盖）。

## 3. 按你的 2A 要点逐条对照

| 你的要求 | 现状 |
| --- | --- |
| Geant4 11.3.2 固定 | `GEANT4_VERSION=11.3.2` 固定；本机实测同一版本 |
| Ubuntu digest / 固定 runner | 使用 `ubuntu-24.04` 标签。**未固定镜像 digest**——GitHub 托管 runner 不允许按 digest 引用，只能在日志里记录实际镜像 |
| 镜像构建只在可信分支 | 未做镜像构建（用 micromamba 装 conda-forge 包，无可信分支问题）；若后续改自建镜像再讨论 |
| 保留 static+GUI 并行，另加 Linux backend+integration | 现有 static/gui workflow 不动；Linux job 只跑 backend+integration，另含构建与数据检查 |
| 每 profile 独立报告 | `…/linux-backend`、`…/linux-integration` 分开，分别过门禁 |
| 依赖缺失即失败 | 两个 profile 步骤都带 `--fail-on-skip` |
| artifact 即使失败也上传 | `actions/upload-artifact@v4` + `if: always()`（后端构建失败时 static/gui 报告仍可上传） |
| 负向病例必须失败（旧 exe/错误数据目录/缺依赖/被篡改日志） | 已实现“被篡改副本日志必须被拒绝”一条；旧 exe、错误数据目录、缺依赖三条尚未单独做负向对照——见下面问题 2 |

## 4. 需要你定的三件事

1. **指纹基线是否跨平台合并**：`source_fingerprint` 只哈希源码内容，Windows 与 Linux 报告现在完全相同。要不要把“Linux 报告必须与 Windows 报告同指纹”写成门禁规则（一旦某平台 checkout 换行不同就会暴露），还是仅记录、不阻断？
2. **artifact 保留策略与负向病例范围**：当前 artifact 默认保留 90 天，报告目录约 200 KB/次（不含日志之外的产物）。你说的四类负向病例，我只做了“篡改日志”一类；另外三类（旧 exe / 错误 `GEANT4_DATA_DIR` / 缺依赖）是否都要进 workflow，还是只保留在本地回归 `scripts/test_report_evidence.py` 的等价断言里？我倾向于后者（CI 时长可控），但需要你确认验收口径。
3. **Linux 报告是否也进 `docs/verification/`**：目前把两份 Linux 报告与日志复制进 `docs/verification/linux-wsl-20261028/`（含 README 与“不证明什么”），理由是证据分支可离线复核；如果你认为 CI artifact 足够、仓库不必存 Linux 副本，我下轮改成只链 artifact。

## 5. 边界（不要据此推断已完成）

- **Actions 未运行**：本机没有 `gh` CLI，读不到 Actions 日志；首次 push 后要看网页才能确认。
- 未做 Geant4 11.2/11.4 矩阵、非 Ubuntu 发行版、真实桌面（非 offscreen）GUI。
- 断言数是已执行 `assert` 的下界，不是覆盖率；门禁只证明报告与日志自洽且未被篡改。
- `git_dirty=true` 的报告：源码指纹与 `tracked_source_gate=pass` 才是判据，工作区是否干净不是。
