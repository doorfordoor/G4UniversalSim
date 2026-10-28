# Linux 构建与验证（本机 WSL 实测，2026-10-28）

本文记录本仓库在 Linux 上的一次真实构建与测试过程，供之后维护 Linux CI 的人复用。**它记录的是一次本机 WSL 实测，不是 GitHub Actions 的运行记录**——CI 的执行结果只能从 Actions 页面读取。

## 1. 为什么要做

`docs/ROADMAP.md` 的 E3 要求"用 GitHub Actions 在 Linux 上构建并跑测试"。在写 workflow 之前先在本机 Linux 上把构建跑通，可以避免把平台相关缺陷留到 CI 里才发现。本机实测一次性暴露了两类只有在 GCC/Linux 上才出现的问题：

- 两处 `G4String` / `std::string` 混用的三目表达式，MSVC 会隐式转换、GCC 直接报错；
- PySide6 在解释器收尾时统一析构 Qt 对象，导致 GUI 冒烟脚本以 `SIGSEGV` 退出（Windows 上不复现）。

## 2. 环境

| 项 | 值 |
| --- | --- |
| 发行版 | Ubuntu 24.04.4 LTS（WSL2，内核 6.18.33.2-microsoft-standard-WSL2） |
| CPU / 磁盘 | 16 核；根分区 1007 G（空闲 935 G） |
| 编译器 | g++ 13.3 |
| CMake | 3.28.3 |
| Python | 3.12.3（仓库自带 `venv`） |
| Geant4 | conda-forge `geant4=11.3.2`（含 Qt5 5.15.15、GDML、全套数据） |
| micromamba | 2.10.0，安装在 `$HOME`（WSL 无免密 sudo，所有依赖只装用户目录） |

### 2.1 装 Geant4（conda-forge）

```bash
mkdir -p "$HOME/bin"
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C "$HOME/bin" bin/micromamba
export MAMBA_ROOT_PREFIX="$HOME/micromamba"
"$HOME/bin/bin/micromamba" create -y -p "$HOME/g4env" -c conda-forge geant4=11.3.2
"$HOME/g4env/bin/geant4-config" --version      # 11.3.2
"$HOME/g4env/bin/geant4-config" --has-feature gdml   # yes
```

conda 的 `geant4` 是元包：装上它同时得到 `geant4-base` 与全部 `geant4-data-*`（下载缓存约 4.1 GB），不需要手写数据集 manifest，也不需要手工下载 3 GB 以上的数据包。

### 2.2 数据集是怎么被找到的

conda 的数据在 `$HOME/g4env/share/Geant4/data/<folder>`，环境变量由 `$HOME/g4env/etc/conda/activate.d/activate-geant4-data-*.sh` 设置。这些脚本依赖 `$CONDA_PREFIX`，因此**只有** `micromamba run -p "$HOME/g4env" -- <cmd>` 才会注入；直接执行二进制拿不到。本机验证时把变量导出一次：

```bash
"$HOME/bin/bin/micromamba" run -p "$HOME/g4env" -- printenv \
  | grep -E '^(G4[A-Z0-9_]*DATA|GEANT4[A-Z0-9_]*)=' > "$HOME/g4env.sh"
set -a; . "$HOME/g4env.sh"; set +a
export LD_LIBRARY_PATH="$HOME/g4env/lib:${LD_LIBRARY_PATH:-}"
```

Geant4 11.3 解析数据集的顺序是：具体的 `G4*DATA` 变量 → `GEANT4_DATA_DIR/<folder>` → 编译时的安装前缀。本仓库的 `--check-geant4-data` 与 `geant4-data.txt`（`Core/Geant4DataLocator`）只负责最后一级的 `GEANT4_DATA_DIR`，具体变量优先，与这个顺序一致。

**各安装布局的目录名并不相同**：Windows 安装包是 `G4EMLOW8.6.1`，conda/发行版是 `EMLOW8.6.1`、`PhotonEvaporation6.1`、`RadioactiveDecay6.1.2`、`RealSurface2.2`（无 `G4` 前缀）。所以 `scripts/test_geant4_data_locator.py` 改成先问后端"这台 Geant4 认哪些目录名"，再在临时目录按这些名字建符号链接来构造数据根，而不是写死任何一种布局。

## 3. 构建

```bash
cmake -S . -B "$HOME/g4build" -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH="$HOME/g4env"
cmake --build "$HOME/g4build" -j 8
```

产物：`$HOME/g4build/G4UniversalSim`（3190904 B）、`$HOME/g4build/mergeHistograms`（90008 B）。配置阶段只有 Qt/EGL 的 RPATH 警告，构建成功。运行时需要 `LD_LIBRARY_PATH="$HOME/g4env/lib"`（RPATH 未覆盖 conda 的 libEGL 等项）。

## 4. 冒烟结果

| 命令 | 结果 |
| --- | --- |
| `--help` | 正常 |
| `--capabilities` | 合法 JSON；solids 15 种；placements `normal/replica/parameterised`；materials 不含 `temperature/pressure` |
| `--check-geant4-data` | `g4usim_geant4_data_v1`，12 个数据集全部 `found: true`，`required_complete: true`，退出码 0 |
| `--config config/main.ini --output <tmp> --dry-run` | 退出码 0（日志中的 `FTFP_BERT_EMZ` 被 `G4EmStandard_opt4` 替换的行为与 Windows 一致） |

## 5. 本机暴露并修复的两类缺陷

### 5.1 `G4String` 与 `std::string` 混用的三目表达式（GCC）

- `src/Geometry/GeometryExport.cc`：`Escape(material ? material->GetName() : std::string())`
- `src/Scoring/TrajectoryRecorder.cc`：`return volume ? volume->GetName() : std::string("OutOfWorld");`

GCC 报 `operands to '?:' have different types 'const G4String' and 'std::string'`；MSVC 会隐式转换，所以 Windows 上一直没暴露。两处都改成显式 `std::string(...)` 转换，并留注释说明原因。全仓复查其它同类三元：只有 `src/Biasing/BiasingMultiParticleXS.cc` 的 `G4String:G4String`，合法。

### 5.2 PySide6 退出时的 `SIGSEGV`（Linux/offscreen）

现象：`gui_plots_backend` 的冒烟脚本已经打印 `smoke_plots_backend: OK`、断言全部通过，进程却以 `-11 (SIGSEGV)` 退出，复现率约 4/5。

gdb 栈：主线程 `PySide::runCleanupFunctions()` → `destroyQCoreApplication()` → `Shiboken::BindingManager::visitAllPyObjects()` → `QObject::~QObject()`。即 PySide 在解释器收尾阶段把仍存活的 Qt 对象统一析构，matplotlib canvas 与父子控件被二次删除。排除过 `fsspec`/`asyncio` 线程关闭（不能修复，仍 4/5 崩）。

修法：在 `QApplication` 仍然存活时显式销毁控件树，而不是留给解释器收尾——

```python
panel.close()
panel.deleteLater()
app.processEvents()
del panel
```

涉及 `gui/smoke_tests/smoke_plots.py`、`gui/smoke_tests/smoke_plots_backend.py`；产品入口 `gui/g4usim_gui/app.py` 的 `run_app` 同样在 `app.exec()` 之后 `window.close()` / `deleteLater()` / `processEvents()`。`smoke_scans*.py` 早就是这个写法，本次沿用同一惯例。修复后连续 5 次运行全部干净退出。

## 6. 测试结果（本机 WSL）

Linux 上执行时显式指定 Linux 产物，并让 Geant4 变量进入子进程环境：

```bash
python -B scripts/run_m0_tests.py --profile backend \
  --require-tracked-sources --fail-on-skip \
  --executable "$HOME/g4build/G4UniversalSim" \
  --merge-executable "$HOME/g4build/mergeHistograms" \
  --report-root "$HOME/reports/linux-backend"
python -B scripts/check_report_evidence.py --report-root "$HOME/reports/linux-backend"
```

结果见 `docs/verification/linux-wsl-20261028/README.md`：backend 与 integration 两个 profile 全部通过，报告通过严格证据门禁（断言级计数、源码/测试指纹、逐用例日志摘要）。GUI 冒烟脚本在 Linux 上以 `QT_QPA_PLATFORM=offscreen` 运行（脚本自身会设置）；`smoke_3d_view` 在 Windows + offscreen 下会切回 `windows` 平台，Linux 上没有这个分支。

## 7. 与 CI 的差异（务必区分）

`.github/workflows/linux-geant4.yml` 用同样的拓扑，但：

| 项 | 本机 WSL | CI |
| --- | --- | --- |
| runner | 本机 16 核 | `ubuntu-24.04` 托管 runner |
| Geant4 | conda-forge 11.3.2 | 同左（`GEANT4_VERSION=11.3.2`） |
| Python | 3.12.3（venv） | 3.11（conda 环境） |
| 显示 | 无（`offscreen`） | 无（`QT_QPA_PLATFORM=offscreen`） |
| 负向对照 | 手动复现 | workflow 内篡改副本日志，断言门禁必须拒绝 |

### 7.1 真实 GitHub Actions 运行（2026-10-28，已在托管 runner 上绿）

`a5970ff` 的两次 push（`codex` run `40634469313`、`roadmap/F6-live-progress` run
`40634465977`）都在 `ubuntu-24.04` 上成功，单次约 12 分 38 秒，18 个步骤全绿：安装
micromamba → 创建固定 Geant4 11.3.2 环境 → 导出数据集变量 → 指向 PySide6 插件 →
cmake 配置/构建 → `--check-geant4-data` → 记录 GDML → Linux static → Linux offscreen
GUI → Linux backend → Linux integration → 四份报告各自过证据门禁 → 篡改报告负向对照
（门禁必须拒绝）→ 上传 artifact。

要让第一次真跑起来，先后修掉三个只在 CI 出现的问题，全部有本地复现：

1. **workflow 级失败（零 job）**：job 级 `env` 里用了 `${{ runner.temp }}`，GitHub 在
   workflow 校验阶段直接判失败（`actionlint` 报 `context "runner" is not allowed here`）。
   改为 `${{ github.workspace }}/.micromamba` 与 `${{ github.workspace }}/.g4env`。
2. **集成套件全灭（Qt 平台插件缺失）**：日志只能看到
   `qt.qpa.plugin: Could not find the Qt platform plugin "offscreen" in ""`。根因是
   conda 环境里 `qt-main`（Qt5）在 `<prefix>/plugins` 放了 Qt5 插件，Qt6 由 python 的
   可执行文件位置推导插件搜索路径，结果只查 `<prefix>/bin/platforms` 与
   `<prefix>/plugins/platforms`（都是 Qt 5.15 插件，被判定 incompatible），
   site-packages 里 PySide6 自带的 Qt6 offscreen 插件从未被搜索。修复：把
   `QT_PLUGIN_PATH` 指向 `PySide6/Qt/plugins`。本机用 conda 环境
   （Geant4 11.3.2 + python 3.11 + PySide6 6.12.0）复现了同样的空搜索路径，并验证
   `QT_QPA_PLATFORM=offscreen` + 该变量后 `QApplication` 正常创建。
3. **公开仓库的 Actions 日志要登录**：直接读日志 403。改为失败时把每个失败用例重发成
   `::error` 注解（`scripts/ci_annotate_failures.py`），run 页面的 Annotations 是公开的；
   正是靠它定位了第 2 条。

仍未验证/未完成：`M0 static and GUI regression`（`m0-static-gui.yml`）在仓库设置里是
`disabled_manually`，所以 Windows/Ubuntu 上那两条 static+GUI 历史 job 不会随 push 触发；
历史（2026-10-23）它们失败在 "Run offscreen GUI tests" 步骤，原因尚未取得（需要日志）。
Geant4 11.2/11.4 矩阵与非 Ubuntu 发行版仍未验证。

### 7.2 第二轮：static 用例 `doc_links` 只在 Linux 失败

第二轮真跑（提交 `7c317e6`，把 static 与 offscreen GUI 也加进同一个 job）在 `Run static tests on Linux` 失败，注解只给出 `AssertionError: doc_links: 5 broken relative link(s)`。本机 WSL 复现得到 5 条断链全部来自历史审计文件 `总体判断.md`：

```
总体判断.md:26: broken relative link 'D:/Geant4/G4UniversalSim/main.cc:170'
总体判断.md:26: broken relative link 'D:/Geant4/G4UniversalSim/src/Core/SimulationManager.cc:247'
...
```

原因：`repo_relative()` 只剥离“当前工作区前缀”，Windows 上 `D:/Geant4/G4UniversalSim/...` 命中该前缀；POSIX 上同一字符串既不是绝对路径也不是当前前缀，于是按相对路径查找而失败。修法是再补一条跨平台回退——剥离仓库目录名（`G4UniversalSim/`）后的部分，并用自检断言两种斜杠形式；修后 Windows 与 WSL 都是 116 链接 / 68 文件 / 0 断链，Linux static profile 7/7 通过。教训同样写进 `docs/agent-history.md`：**只在 Windows 跑过的 static 用例不能算跨平台通过**。

## 8. 不证明什么

- 不证明 Linux 上任何物理结果与 Windows 一致——测试只覆盖配置、生命周期、文件契约与物理量在给定容差内的既有断言；
- 不证明 GUI 在真实桌面环境（X11/Wayland 非 offscreen）可用；
- 断言数是"已执行断言的下界"，不是覆盖率；
- 本文档中的路径是本机 WSL 的实际布局，CI 中由 `${{ runner.temp }}` 生成。
