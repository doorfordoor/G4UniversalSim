# 2C 配置阶段基础链路验收（2026-10-29）

本轮实现类型化配置快照、只读导出、GUI 查看器。**这是完整 2C 的配置阶段子集，最多 15 个 Manager 字段，不是完整阶段验收。** [实现范围与消费者清单](../../EffectiveConfig.md)。

## 实际结果

- Windows / MSVC 19.51.36246.0 / Geant4 11.3.2 / Release / MT 构建成功。
- 统一平台 **89 PASS / 0 FAIL / 0 SKIP，117149 条探针断言**：static 10 / GUI 28 / backend 36 / integration 15。独立 C++17 模型另有 24 条 Python 探针断言（含编译及 C++ 不变量程序的退出检查，g++ 15.1.0），不并入 89 项。
- 为缩短复测等待，分两组执行：[backend 36 项](backend/report.json) 与 [static/GUI/integration 53 项](ui-integration/report.json)。后者是 `--profile all` 加显式 `--case` 选择，不是另一次全 89 项。集合交集为空、并集与统一平台 CASES 恰好相等；两报告均逐项非零断言、tracked source 门禁通过、无 fail/skip，分别过严格证据门禁。
- [coverage.json](coverage.json) 仅汇总两个原始报告的集合、哈希与统计，不重写或替代原报告。原报告及 89 份日志按原始字节复制；归档后重新校验日志 SHA-256。源码及测试指纹与当前文件核对一致。
- [独立模型日志](model/logs/effective-model.log)；GUI compileall 与 diff 空白检查通过。另用中文 INI 文件名、中文运行名核对真实导出的值与来源路径，往返通过。

| 证据身份 | 值 |
| --- | --- |
| 源码指纹 | `00900102950df94a4a31b61ab7f9c3f9b6ac3ca7e5d2074b8f2e0bcb09d1456e` |
| 测试/夹具指纹 | `14191c3262b0d81614fb542f8bcea8313989124fcc539da590b73766e8d44b2c` |
| 后端 SHA-256 | `2f0bb10490078360a4fcdb13f624ac3237a9521f5a6cd2c262d8486023fe15d6` |
| 后端字节数 | 1785856 |
| 报告探针 / 摘要 | settrace_assert_lines_v2 / sha256_raw_bytes_lf_v2 |
| 执行时 Git 状态 | 基线 5465dbd，开发改动尚未提交；不是声称旧提交已含新功能 |

## 真实界面检查

加载 [真实后端导出 JSON](visual/snapshot.json)（归档示例仅将 stdout 的 CRLF 转为 LF，JSON 值未改），查看了 [浅色](visual/effective-config-light.png)、[深色](visual/effective-config-dark.png) 与 [760×600 小窗口](visual/effective-config-compact.png) 的 offscreen Qt 截图。主体获得剩余高度，树与详情可同时阅读，小窗口保留滚动。渲染脚本显式加载本机微软雅黑解决 offscreen 字库缺失，不修改产品字体或用户设置。本轮未做真实桌面交互、高 DPI、多屏与辅助技术验收。

## 初轮失败与复测

首轮为 87 PASS / 2 FAIL / 0 SKIP，原报告仍在 `out/verification/2c-all/20261029-103107-dfa81a1c/report.json`，未把失败涂改为通过。

1. 新构建放在 `out/build-effective`，能力测试的默认 `build*/CMakeCache.txt` 搜索无法找到 GDML 预期。构建实际启用 GDML；通过现有 `G4USIM_EXPECT_GDML=1` 明确预期，复测通过。
2. 普通用户创建临时目录符号链接触发 WinError 1314。使用测试已有的 `G4USIM_GEANT4_DATA` 参数指向安装数据根，复测通过；没有提权或修改系统权限。该分支没有临时镜像数量检查，因此此用例 51 条断言，历史镜像分支 52 条，未声称逐用例断言数量完全不变。总断言高于历史 116677，所有用例非零。

最终两组都采用上述明确环境，且包含查看页布局修正；不能把初轮旧布局的结果当作最终证据。

## 复现与边界

```powershell
$env:G4USIM_EXPECT_GDML='1'
$env:G4USIM_GEANT4_DATA='D:\ProgramFiles\Geant4\share\Geant4\data'
python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip --executable out/build-effective/Release/G4UniversalSim.exe --merge-executable out/build-effective/Release/mergeHistograms.exe --report-root out/verification/2c-recheck
python -B scripts/check_report_evidence.py --report-root docs/verification/2c-configured-20261029/backend
python -B scripts/check_report_evidence.py --report-root docs/verification/2c-configured-20261029/ui-integration
python -B scripts/test_effective_config_model.py
```

新代码的 Linux / Geant4 11.4 / CI / 冻结安装包尚未验证，历史矩阵绿不能替代本轮验证。原 `effective_*` 摘要和物理行为兼容回归通过；本轮没有新增独立物理基准。完整来源链、输入哈希、全模块对象覆盖、运行开始/最终化快照、off/auto/on、GUI 差异视图仍待完成。原 DSH 工作区未合并。
