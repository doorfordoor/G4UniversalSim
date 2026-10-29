# R32 非 csh 原生 UI 会话边界

## 提案与确定证据

冻结前 main.cc:1010–1011 直接创建 G4UIExecutive 并进入 SessionStart，绕过仅在 AuditedCshSession 回调内实施的 R26 随机语义与 R30 run 生命周期守卫。原生 Geant4 11.3.2 G4RunMessenger.cc:519–535 对单个 setSeeds 仅打印 ignored，对固定 seeds[100] 无输入数量边界且随后写终止零；因此公开入口可重新触达已确认的假成功/内存安全路径，不只是未覆盖所有 UI 测试。main 非 csh 收尾未取得这些原生命令的语义失败状态。本次只读复核没有启动 Qt，不宣称已实际复现 Qt 崩溃。

最小修复：保留原有 biasing preflight 后、sim.Initialize 前，按最终 context interactive 状态拒绝非 csh 执行会话，诊断包含 `requires --ui-session csh`；同时覆盖 CLI 裸 --ui 与 INI interactive=true。禁止静默降级或 unsafe 绕过开关。删除 native G4UIExecutive 分支并保留防御拒绝。dry-run 不进入会话，允许裸 --ui。Python 桌面 GUI 的正常 Run/后端几何预览调用 config/macro，不依赖原生 --ui，因此继续保留。

官方证据：https://raw.githubusercontent.com/Geant4/geant4/v11.3.2/source/run/src/G4RunMessenger.cc 。本提案不扩大为任意第三方内核调用或全部 Geant4 动态命令的审计保证。

## 文件清单与验收

- root：main.cc 实施入口/防御拒绝及 help；根 AGENTS、agent-history、ROADMAP 和发布契约由 root 集成。
- geometry：scripts/test_interactive_commands.py 增加 CLI 裸 --ui、INI interactive=true、裸 --ui 带合法 echo sentinel + beamOn macro 三反例；均须非零、failed 摘要、run_count=0、无 sentinel/事件文件。现有 csh 正例保留；新增裸 --ui + dry-run + 同 macro 正例，须 dry_run、零 run、不执行 macro。
- geometry：gui/AGENTS.md 与 docs/功能支持矩阵.md 同步当前 R32 事实，不追改历史记录。

测试使用 G4USIM_EXE，无新盘符路径；本次只做 Python 语法与差异静态检查。真实反例须等 root build7，不能用旧 build6 声称通过。

构建7真实验收：统一targeted7/20261029-175350-e4b608c3，interactive_commands通过298个v3断言入口，包含三类入口拒绝/dry-run正例及既有csh链路；4项专项整体通过3893个入口，严格证据门禁通过。最终全量/平台证据另存，不以此替代。
