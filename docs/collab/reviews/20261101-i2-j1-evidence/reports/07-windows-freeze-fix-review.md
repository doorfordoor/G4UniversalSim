# Windows freeze / QtCore 失败修复独立窄审查（2026-11-01）

结论：所审逻辑未发现阻断缺陷，可以继续完整package邻接自检与实际运行验收。未重建整包，未修改产品或正式测试。

## 已核查实现与影响边界

- packaging/windows_freeze.py:11-18仅产生子进程环境副本；移除PYTHONPATH/PYTHONHOME/QT_PLUGIN_PATH/QT_QPA_PLATFORM_PLUGIN_PATH，PATH限selected Python executable目录、base Python/DLLs与Windows/System32，父进程环境不变。这能阻断本次Poppler/libheif污染来源，不声称隔离所有PyInstaller hook或所有宿主配置。
- packaging/windows_freeze.py:21-48从实际Analysis-00.toc递归取BINARY/EXTENSION，resolve后按目录包含关系核对sys.prefix/base_prefix/SystemRoot/work；空收集也失败。work-other不被work前缀误认；不以字符串startswith放行。审计依赖来源而非DLL符号/ABI正确性，后者仍需真实启动。
- packaging/build_package.py:145-149、164-168，GUI与Python helper两个实际PyInstaller调用均传清理后的env；仅returncode0后审计，审计成功后才返回产物目录，没有绕过失败。
- gui/main.py:14-37，只有带--self-test的异常进入启动失败报告路径；普通用户启动仍抛出原错误。失败报告新文件exclusive写入，已有证据不覆盖；返回1。捕获的是Python异常，不承诺拦截bootloader/native crash或Windows进程启动前错误。报告写入目标不可写时仍退出1，stderr可用时输出诊断。

## 根因材料核对

out/collab/i2-qt-icu-root-cause.json记录旧包icuuc缺Qt6Core所需20个符号，对照System32版本无缺符号；与外部PATH采集错误DLL的解释一致。新out/package-build-qtfix/binary-sources.json实际523条均allowed、没有打包icuuc条目。本轮没有自行重做PE依赖遍历，也没有把审计通过等同Qt启动成功；root另有真实Qt导入与完整package邻接验证链。

## 独立验证

使用原D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe：
1. scripts/test_frozen_startup.py退出0：ImportError失败新报告/exit1、旧证据保持、普通启动仍失败，以及外部DLL来源拒绝。
2. 新out/collab/review_windows_freeze.py退出0，证据windows-freeze-fix-review-evidence.json：四个污染环境变量全部仅在子环境清除；EXTENSION外部来源、work sibling路径、空TOC全部拒绝；合法嵌套BINARY/EXTENSION接受；实际新build审计523/523、disallowed0。

## 负例与剩余验收边界

- 新startup负例在源码入口注入ImportError，适合验证报告控制流，不能独立证明PyInstaller bootloader无对话框或全部Qt插件运行正常；完整冻结exe实际自检与自然退出应由主任务已有构建继续完成。
- 审计只证明收集来源，不证明实际发布包字节与TOC一致、所有插件可用或离开本机仍可运行。正式包字节清单、无Geant4/Python/PATH的干净系统验证仍保留I2原验收责任。
- 本轮未发现需要为修复此故障而扩大更改的缺口；首次在孤立freeze目录自检缺scenarios与QtCore导入根因分开记录，不能混作原DLL修复失败，也不能抹掉该次失败。
