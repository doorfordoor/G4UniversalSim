# H3-5 Linux 编译类型修复回执（2026-11-07）

依据主审授权（m25273）：只修原 Linux CI 暴露的一行 GCC 类型歧义；不提交/不 push、不重跑旧 CI，
不扩范围。原四云其余收集继续，未被打断。

## 失败与修复

- 原提交 `ec84f90aba62a876c614600bdac73ec70cb745df`；Linux 两个 task 均在构建失败：
  `run 42301679239` jobs `128180755222`（11.4.3）/`128180755055`（11.3.2）step「Build the backend」；
  `run 42301679482` job `128180755925`（11.4.3 installation）step「Configure and compile Linux backend」。
- 最短错误：`src/ParallelWorld/ParallelScoringDetector.cc:198:41: error: operands to '?:' have
  different types 'const G4String' and 'std::string'`（GCC；MSVC 接受）。
- 唯一修改（`src/ParallelWorld/ParallelScoringDetector.cc:198`）：
  `volume->GetName()` → `std::string(volume->GetName())`，两臂同类型；名称/unknown 回退/路径/物理量/
  输运/RNG 不变。

## 验证

- GCC 13.3 + Geant4 11.4.3（WSL，`-fsyntax-only`）：修复后 `POST_FIX_COMPILE_OK`；反向还原对照
  `PRE_FIX_COMPILE_FAIL` 并在同一行复现原错误。
- Windows MSVC 本地重建：exe `42b37beba7de2f1cb2547a148052216b779b5b74b6a7d6b88139026969061e30`、组件
  `9bc14e2e0f88f1c7efb5da2ac3a0c943d87a1f04f1ec345e694054f9caa74248`；D 工作区 fingerprint `11effa5a1733dd4b0d462adf1425b2e4b6a51931377bb4ec92b801dfdabac0e2`
  （dirty 为任务前既有 H8 未提交改动）；canonical 新指纹待主审在干净 checkout 复验。
- 既有专项：`test_parallel_world.py` OK；`test_parallel_scoring_component.py` OK（21 checks）。

## 证据

`out/collab/20261107-h3-linux-type-fix/`：`fix.diff`（11 行，SHA-256
`63a8f1788ca265d5cf80f93cd30eb585888f8644e3562c572acf363f8d951a80`）、`identities.json`（SHA-256 `e419c8b5e06126163a3c71d15b5da02a92254d6847a21f3e552f4c9b4d4f917e`）、
`logs/local-build.log`、`logs/test_parallel_world.log`、`logs/test_parallel_scoring_component.log`、
`logs/gcc-syntax-check.log`、`gcc/syntax-check.sh`、`README.md`。

## 边界与下一步

- 未提交、未 push；原四云未重跑/未取消；旧科学 `3700e272…`/`c7de5a3c…` 与工程 `802ad812…` 原样保留。
- H3-5 仍失败；等主审复验该修复并在干净 canonical 源冻结新候选后，由既有自动四云触发新运行。
- 未改产品其它位置、CI、打包、工具、固定合同/清单、CURRENT/ROADMAP。

停写等待独立评审。
