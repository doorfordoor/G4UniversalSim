# J3 首次正式冻结候选：4eebbe9e（未关闭阶段）

主审独立检出 C:/Users/123/.codex/worktrees/j3-final/G4UniversalSim，git_head=4eebbe9e2003c8b0ea6d5fac48df9e9cfa746e67，git_dirty=false，tracked_source_gate=pass。原C盘effective-config保留。此目录保存本候选原报告及逐例logs，不代表后续修复候选，也不代表J3整体验收。

| 层 | 用例 | 断言 | 结果 |
|---|---:|---:|---|
| static | 49 | 5672 | 49通过、0失败/跳过，严格自洽门禁通过 |
| gui | 77 | 10822 | 77通过、0失败/跳过，严格自洽门禁通过 |
| integration | 33 | 6830 | 33通过、0失败/跳过，严格自洽门禁通过 |

source_fingerprint=9e40e889d49a…；tests_content_fingerprint=4b02d021912b…。GUI新增VTK用例210断言实际执行。integration通过含真实后端、轨迹等原定用例；这些测试不等于独立科学/物理验证。

命令为 scripts/run_m0_tests.py --profile <static|gui|integration> --require-tracked-sources --fail-on-skip；integration显式提供D盘现有G4UniversalSim.exe和mergeHistograms.exe路径；设置G4USIM_GEANT4_DATA=D:/ProgramFiles/Geant4/share/Geant4/data。static前置D:/msys64/ucrt64/bin。GUI解释器D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe。运行根out/verification/j3-final-4eebbe9e，完整外层输出out/collab/j3-closeout-release/independent-<profile>.log。

重要边界：该GUI运行依赖复制到干净检出的gitignore目录gui_runs，这是云端失败发现前保留的真实环境事实。不能把本地通过外推到没有该目录的云检出。修复此隐含依赖已经派工，原报告保持不改。static比旧E1少15条断言，集中于install_plan(-6)、k1_bundle(-7)、k1_staging_alias(-2)，脚本未更改，路径/链接分支映射仍待定向核实，不靠改断言凑数。

## 真实云 CI

- Linux run41737057191，双Geant4版本均GUI失败：Export agent bundle底边超workspaceShellScroll 1像素；gui_theme_state期望结果树非空实际0。原失败保留，最小修复任务j3-ci-minimal-fix-4eebbe9e-20261104，回执round26 accepted。
- desktop-package run41737057233成功，Windows/Linux产物分平台，不代表Linux回归成功。
- M0 run41737057247与installation41737057220最近核查仍运行中。

复核：python -B scripts/check_report_evidence.py --report-root docs/verification/j3-candidate-4eebbe9e-20261104/<profile>。全部原定门禁通过后才可关闭J3。
