# Windows 全量回归证据 — 2026-10-28（E3 Linux 支持与可移植性修复后）

## 报告事实

| 项 | 值 |
| --- | --- |
| 命令 | `python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip --report-root out/verification/stage1f-20261028` |
| run | `20261028-115816-42b2e7c6` |
| 结果 | 80 pass / 0 fail / 0 skip |
| 断言 | `assertions_executed_total = 116201`，`assert_sites_total = 2417`，`cases_with_zero_assertions = []` |
| 分层 | static 6 / backend 34 / gui 26 / integration 14 |
| `source_fingerprint` | `5bd97ec5e96e85f83b35b6d33d82ea12493e9d2eb4d78902c8d2ba5165d13206` |
| `tests_content_fingerprint` | `6fb2303906a4c1f29b3c26d052f3a938532d9a6ef3ae57433aa87f4ab107fda8` |
| `backend_provenance` | `source_sha256_manifest_matches_executable` |
| `git_head` / `git_dirty` | `32736c9` / true（运行时含本轮未提交改动） |
| exe | `build_vs2026/Release/G4UniversalSim.exe`，SHA-256 `dd62fd8748fba532a12842881b0a680dff11816a6031724fd4caf9ecd83cde1f`（1734656 B） |
| 构建 | MSVC 19.51.36246.0 + Geant4 1132 + MT |
| 门禁 | `report evidence: OK … version 2, profile all, 80 cases, 116201 assertions executed, probe settrace_assert_lines_v2, digest sha256_raw_bytes_lf_v2` |

## 本轮做了什么

- E3 Linux CI 准备：新增 `.github/workflows/linux-geant4.yml`，并在本机 WSL Ubuntu 24.04 +
  conda-forge Geant4 11.3.2 上验证同一拓扑；Linux 侧证据见
  `docs/verification/linux-wsl-20261028/`（backend 34/34、integration 14/14），构造与结论见
  `docs/Linux构建与验证.md`。
- 由 Linux 暴露并修复：两处 `G4String`/`std::string` 三目混用（GCC 无法编译）与 PySide6 解释器
  收尾析构导致的 `SIGSEGV`（控件树必须在 `QApplication` 存活时销毁）。
- `scripts/test_geant4_data_locator.py` 改为从后端报告推导数据集目录名并在临时目录建符号链接，
  不再写死 Windows 安装路径、不再在缺数据时以 SKIP 退出 0。
- `scripts/check_report_evidence.py`：日志副本优先按报告目录解析；`--allow-incomplete` 接受没有
  退出码的 skip 记录（未运行的用例没有退出状态）。

## 复现

```bash
cmake --build build_vs2026 --config Release --target G4UniversalSim
python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip \
  --report-root out/verification/stage1f-20261028
python -B scripts/check_report_evidence.py --report-root out/verification/stage1f-20261028
```

## 不证明什么

不含 GitHub Actions 的运行结果；不含 Geant4 11.2/11.4 的兼容性；不断言物理结果与 Linux 逐位一致
（对照的是同一 `source_fingerprint`/`tests_content_fingerprint` 下的既有断言）；断言数是下界而非覆盖率。
