# 阶段 0 审计修复的验收证据（2026-10-27）

本目录保存阶段 0（提交 `2e87f18`）的完整回归与性能证据副本。`/out/` 与 `/build*/` 被
`.gitignore` 忽略，原始报告不可复核，因此把关键文件复制进来，作为可 review 的验收记录。

## 内容

| 文件 | 说明 |
| --- | --- |
| `report.json` | 统一测试平台 `--profile all --require-tracked-sources` 报告，**76 PASS / 0 FAIL / 0 SKIP** |
| `logs/` | 同一轮的逐用例日志（`run_m0_tests.py` 写出，原样复制） |
| `performance-final.json` | F6 进度遥测开销的成对采样结果（12 组交替、中位比值 1.0047） |
| `performance_probe.py` | 生成 `performance-final.json` 的脚本副本（原位置 `out/verification/f6-20261027/`，被 git 忽略） |

## 报告事实（report.json 实测值）

- `profile=all`、`platform=Windows-10-10.0.26200-SP0`、`python=3.11.9`
- `git_head=2e87f18ef2b45b0d6e928c37d2e58bee51720af7`
- `source_fingerprint=9ea49a045ec58d9aef6164f24a181150bef36091608b799cf12bf08ecec991a7`
- `backend_provenance=source_sha256_manifest_matches_executable`
- `merge_source_fingerprint=ebfde9055d9a82cc855562869ff425a02f63e4346174dd2b9977e50f19c84106`、
  `merge_provenance=source_sha256_matches_executable`
- `backend_build_identity`：Release、MSVC 19.51.36246.0、Geant4 1132、multithreaded=true
- `tracked_source_gate=pass`、`untracked_source_files=[]`
- 分层：static 3 / gui 26 / backend 33 / integration 14 = 76，全部 `pass`
- `git_dirty=true`：报告运行时工作区只有文档改动（ROADMAP、开发路线图、F6 检查点），
  C++/GUI 运行时源码与 `2e87f18` 完全一致，随后这些文档改动单独提交；报告不覆盖提交后的
  文档内容，也不代表源码指纹包含 `scripts/`、`schema/`、`config/`。

可执行文件 SHA-256（与上述源码指纹对应）：

- `build_vs2026/Release/G4UniversalSim.exe`：`8f6df0fef6554c9897be8a249c1d6af9e26bd17378660c3f7fcc39fa02f20e22`
- F6 改前基线 `build_vs2026/Release/G4UniversalSim_f6_baseline.exe`：`20385dd57c51d77bf9d688302d2838591492eff0c12b996c2940cbf27357b91e`

## 性能证据的读法

`performance-final.json` 使用成对设计：两个二进制各先 warm-up 一次，12 组交替顺序采样，
每组记录 `candidate/baseline` 比值。结果：中位比值 1.0047，最小 0.9706，最大 1.0519；
中位墙钟 baseline 5.402 s、candidate 5.390 s；候选每次仍产生 8–9 条 running 进度更新。
同一报告的 `drift_check` 给出前三分之一中位比值 1.0266、后三分之一 0.9801，说明本机墙钟
存在约 ±3 % 的随时间漂移。因此只能声明"F6 进度遥测开销低于本次测量噪声（约 ±3 %）"，
不能声明精确开销百分比；更早的 group-median 版本给出 1.068，是漂移假象，不得引用。

## 复现命令

```bat
cmake --build build_vs2026 --config Release --target G4UniversalSim
python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --report-root out/verification/stage0-20261027
python -B out/verification/f6-20261027/performance_probe.py
```

## 本证据**不**证明

- Linux/GitHub Actions 上的 Geant4 后端（CI 仍只跑 static+gui）；
- 任何新增物理基准（本轮没有改物理实现，B1 只是名字解析与失败边界）；
- PyVista 3D 视觉、高 DPI 与人工 GUI 交互验收；
- 全部 Messenger 命令族的动态路径审计（本项只闭合 B1–B4 与 detector/seed 三条命令）；
- ROOT 多线程合并之外的线程规模（既有 `root_output` 用例覆盖 2 线程 × 2 run）。
