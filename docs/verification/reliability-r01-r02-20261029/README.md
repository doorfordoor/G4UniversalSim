# R-01 / R-02 修复验收

2026-10-29，在隔离分支 `roadmap/2c-effective-config`、HEAD `d286577` 加本轮未提交源码上完成 Release 构建和完整统一回归。

- **89 PASS / 0 FAIL / 0 SKIP，117833 条已执行断言**；89 个用例全部非零断言，与 2C 子集归档的 89 用例集合相同，总断言由 117149 增至 117833。增加 684 不是代码覆盖率或物理可信度分数。
- `profile=all`、报告 v2、`tracked_source_gate=pass`、`backend_provenance=source_sha256_manifest_matches_executable`、`skip_policy=failure`；`settrace_assert_lines_v2` / `sha256_raw_bytes_lf_v2`。原始与归档报告均通过严格 `check_report_evidence.py`，逐日志摘要与实际字节相符。
- 构建：MSVC 19.51.36246.0、Geant4 11.3.2、MT、GDML、Release。后端 SHA-256 `4658f847bb29cd91d42eda9f52931207f7762ea0374947fa27ac364007ab2acd`。
- 源码指纹：`a75a3fb0d8d79c8fbc92e77c82101dac024735039962ba8477c10ead3b6267f8`；测试/夹具指纹：`10b9de8cec4f4399c27ccf7a33fbcbe8c9e57ef7ccc4b02eb711e58d584ae444`。报告中的 git_dirty 为 true，指纹和构建身份用于核对真实内容，不冒称运行时已有最终提交。

证据：[report.json](report.json) 与 logs 中 89 个逐用例日志；从 `out/verification/reliability-r01-r02-20261029/20261029-115233-96d13470/` 按字节复制后复核门禁，未改写失败/断言或日志内容。

## 修复及新增反例

- R-01：csh 在配置后拒绝 `setMainConfig` 时登记 app 失败、停止后续输入、非零退出并写 failed 摘要。单/双线程 × PreInit/已初始化四种反例均检查零 run、未执行后续 echo/beamOn、原配置与来源保持。完整热重载仍不支持。
- R-02：metadata 打开/写入/关闭异常锁存首因；仍可写的文本摘要被纠正为 failed/非零退出码，失败 JSON 不列作产物。真实目录碰撞、写入/关闭注入、单/双线程、多 run 保留、首因优先与正常 text/JSON 一致均通过。
- 关键专项：`interactive_commands` 273 条断言，`run_summary` 2599 条断言；既有命令状态/优先级、输出、ROOT、GUI 结果判定与全套集成也通过。

复跑入口：GUI venv Python 运行 `scripts/run_m0_tests.py --profile all --executable out/build-effective/Release/G4UniversalSim.exe --merge-executable out/build-effective/Release/mergeHistograms.exe --report-root <新目录> --require-tracked-sources --fail-on-skip`。本机构建目录非默认 build 名称，因此显式设置 `G4USIM_EXPECT_GDML=1`、`G4USIM_GEANT4_DATA=D:\ProgramFiles\Geant4\share\Geant4\data`；这是机器参数，不写入测试脚本或产品默认路径。

## 边界

本轮只验收 Windows 11.3.2 上 R-01/R-02 及回归兼容，没有重跑 Linux/11.4 CI、真实桌面多屏或安装包。metadata 故障注入是规定边界测试，不代表真实磁盘满/断连；文本和 JSON 不具备跨文件原子提交保证，失败 JSON 可能存在且看似完整，必须以失败状态/产物登记识别。

R-03/R-04 在同一个新后端上仍可真实复现，见 [独立反例证据](../r03-r04-current-20261029/README.md)。R-05–R-07 与 V-01 仍待后续处理。不能把本报告全绿当作这些新反例已经覆盖、整个修复批次关闭或完整 2C 完成。
