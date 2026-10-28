# Linux（本机 WSL）验收证据 — 2026-10-28

**这是本机 WSL Ubuntu 上的实测证据，不是 GitHub Actions 的运行记录。** Actions 是否通过只能看
仓库的 Actions 页面；本机没有 `gh` CLI，无法读取那里的日志。

## 1. 环境

| 项 | 值 |
| --- | --- |
| 发行版 | Ubuntu 24.04.4 LTS（WSL2） |
| Geant4 | conda-forge `geant4=11.3.2`（GDML `ON`，含全部 `geant4-data-*`） |
| 编译器 | g++ 13.3 |
| CMake | 3.28.3 |
| Python | 3.12.3（虚拟环境，`uproot`/`PySide6`/`matplotlib` 来自 `gui/requirements.txt`） |
| 后端 | `/home/u123/g4build/G4UniversalSim`，SHA-256 `fea629faf94b76aec5cb8185572ba2c83decf5c9df1b468339bd26e98f02aedb` |

构建命令与数据集布局见 `docs/Linux构建与验证.md`。

## 2. 证据

| profile | 用例 | 断言 | 报告 |
| --- | --- | --- | --- |
| `backend` | 34 pass / 0 fail / 0 skip | 109853 | `linux-backend/report.json` + `logs/`（34 个） |
| `integration` | 14 pass / 0 fail / 0 skip | 4324 | `linux-integration/report.json` + `logs/`（14 个） |

两个报告都通过严格证据门禁：

```bash
python -B scripts/check_report_evidence.py --report-root docs/verification/linux-wsl-20261028/linux-backend
python -B scripts/check_report_evidence.py --report-root docs/verification/linux-wsl-20261028/linux-integration
```

实测输出（`version 2`、`probe settrace_assert_lines_v2`、`digest sha256_raw_bytes_lf_v2`）：

- backend：34 cases、109853 assertions，`source 5bd97ec5e96e…`、`tests 6fb2303906a4…`；
- integration：14 cases、4324 assertions，同一 `source`/`tests` 指纹。

`source_fingerprint` 是**源码内容**指纹（与平台无关）：本机 Windows 的全量报告与这里的 Linux
报告都得到 `5bd97ec5e96e85f83b35b6d33d82ea12493e9d2eb4d78902c8d2ba5165d13206`，`tests_content_fingerprint`
也相同（`6fb2303906a4c1f29b3c26d052f3a938532d9a6ef3ae57433aa87f4ab107fda8`）。因此"同一份源码在
Windows 与 Linux 上都通过"这件事可以由指纹直接对照，而不是靠文字声明。

同一份源码的 Windows 全量参考（`out/verification/stage1f-20261028/20261028-115816-42b2e7c6`，
证据副本见 `docs/verification/stage1f-20261028/`）：80 pass / 0 fail / 0 skip、116201 断言、
exe SHA-256 `dd62fd8748fba532a12842881b0a680dff11816a6031724fd4caf9ecd83cde1f`。

## 3. 这些证据证明了什么

- 本仓库能在 Linux（Ubuntu 24.04 + GCC 13 + Geant4 11.3.2）上配置、构建并运行；
- 全部 34 个 backend 用例与 14 个 integration 用例在该平台上通过，包括真实 Geant4 运行、
  ROOT 输出对账、GUI offscreen 冒烟与 GUI↔后端一致性检查；
- 本轮由 Linux 暴露并修复的两个缺陷已在代码中（`G4String`/`std::string` 三目混用、PySide6
  退出 `SIGSEGV` 的控件树销毁顺序），见 `docs/Linux构建与验证.md`。

## 4. 不证明什么

- 不证明 GitHub Actions 上已通过（workflow 已写，但本机无法读取 Actions 日志）；
- 不证明 Geant4 11.2 / 11.4 或非 Ubuntu 发行版可用；
- 不证明 Linux 与 Windows 的物理结果逐位一致（测试判据是既有容差下的断言，不是逐位比较）；
- 不证明 GUI 在真实桌面（X11/Wayland 非 offscreen）可用；
- 断言数是"已执行断言的下界"，不是覆盖率；
- 报告里 `git_dirty=true`：运行时的源码包含当时未提交的改动（`git_head=32736c9`），
  证据的可信度靠 `source_fingerprint` 与 `tracked_source_gate=pass` 判定，而不是靠工作区是否干净。
