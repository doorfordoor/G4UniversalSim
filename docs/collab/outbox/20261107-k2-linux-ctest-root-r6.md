# K2-3 Linux 默认 CTest 根目录最小修复（r6）

主审指令：m28583（K2-3 同一任务的最小前置 r6），冻结决定：

- `docs/collab/decisions/20261107-k2-linux-ctest-root-minimal-fix.md`

## 产品变更（仅一行）

`CMakeLists.txt` 的 `h2_volume_scoring_check` COMMAND 增加第二个参数：

```text
COMMAND h2VolumeScoringCheck ${PROJECT_BINARY_DIR}/h2-component-output ${PROJECT_SOURCE_DIR}
```

复用 `tools/h2VolumeScoringCheck.cc` 已支持的 argv[2] repository 参数；未修改 C++、二进制/输出布局、夹具位置、组件测试名称或标签。

## 模板与导出身份

- 旧模板身份（冻结候选）：`1fa4e294…`（309 成员 / 3,819,706 B，历史）
- 新模板身份：`36324640f5222558eca67919f42829fed8fa68815c128afe07f9ce85dc566e74`
  - 成员 309 / 字节 3819728
  - manifest SHA-256 `51d76103dbf4b098c4a3661769ee4f1db290a1e9d3f3fd8df672b1e2c74e8776`
- r6 新导出（S-A）payload identity：`68d5e82ee356cd02a7a08fc824d3fab04e91f30d95df37ed2d903fa0b11cda01`（318 文件），template matched。

## Linux 默认 single-config 配方验证（新 CMake）

- 导出 → `cmake -S . -B build_linux -DCMAKE_BUILD_TYPE=Release -DG4USIM_STANDALONE_EXPORT=ON -DCMAKE_PREFIX_PATH=/home/u123/g4env`
- configure/build exit 0
- 二进制：`G4UniversalSim` `36a9023adf40a14ea5c9c09c345345633c91436aa9adf73fdd52626ce6839d25`，`parallelScoringCheck` `c0ab5dde8931cd827eb9d1448ccfa065393759d92cfee826c23c44e7866d19e2`，`h2VolumeScoringCheck` `3e0502516c80bcc9145026c7eda338f301064cc45d438c14f2ed2e72d7583b32`
- source_fingerprint：`3d414de07b3d95e6e1c8f669e2fcb26d8109021eb5b23d805d2a49a4c982ed07`（新 CMake 属于编译身份输入）
- `ctest --test-dir build_linux -L "^component$"` → 2/2 通过；日志 `out/collab/20261107-k2-build/linux/ctest.log`

## 专项自测

- `python -B scripts/test_k2_project_export.py`：pass（files=318 identity=68d5e82e… template=36324640…）
- `QT_QPA_PLATFORM=offscreen python -B gui/smoke_tests/smoke_export_project.py`：OK
- `python -B packaging/export_template.py --root . --check`：ok，problems=[]
- `scripts/check_doc_links.py`：1505 链接 / 535 文件 / 0 断链

## 保留的失败与限制

- 修复前 Linux 单配置 h2 CTest 失败（缺 `scenarios/semiconductor/niel/si_proton.csv`，根目录推导多一级）：`linux/linux-ctest-run.txt`
- Ninja Multi-Config 仅诊断，不替代默认配方：`linux/linux-ctest-multi-run.txt`
- 首次 Linux P7 因 shell 引号失败：`linux/linux-p7-run.log`
- Windows 模块捕获 exit=null 记为 unknown（运行摘要 200 事件另证完成）
- `verify_export` 对运行后的额外运行输出拒绝（运行输出不属于密封导出闭包；规则未改），P8 用运行前验证留证

## 未执行

Windows 用新 CMake 重建、r6 二进制 200 事件运行、Linux 依赖独立性、完整 profile、云 CI、安装包、K2-3 剩余矩阵；均由主审冻结后回原 K2-3 继续。

## 当前状态

- HEAD `ad8b8e34e39679f444b223d31b2e0b8c3f1995e4`（分支 `roadmap/Q2-scientific-baselines`）；未提交、未推送
- 本轮修改仅：CMakeLists.txt、scripts/test_k2_project_export.py、packaging/export_template_manifest.json、docs/独立工程导出.md
- 回执：`out/collab/20261107-k2-implementation/author-r6/receipt.json`
