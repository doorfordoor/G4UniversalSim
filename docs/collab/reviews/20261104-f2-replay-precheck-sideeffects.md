# F2 重放预检副作用独立反例

结论：确定为缺陷，实际结果不一致。限定修复中3b dirty构建，C++指纹bc8cec3040d3477e2f089d4c169e18f062417e609a261f620b487f2ec8365b0f；独立复制exe隔离运行，原二进制SHA见copied-build.json，非最终冻结候选。

同一原会话第一轮直接run沿用主配置源，第二轮才set_source energy=200MeV，各5事件。所有正常关闭后新进程重放。原始计划合法，无篡改。结果：原/replay event_edep第0轮event0已不同；hits键原5837/replay669。后台仍exit0/replay_finished。

定位：src/Core/SessionServer.cc预检全部replaySteps时调用ApplySourceEdit真的改源，后轮参数污染尚未执行的首轮。要求原本的无副作用整计划语义校验（或完整恢复，包括所有源几何状态），然后严格按序执行。最小既有文件修复/用例，不扩工具。

证据：out/collab/f2-replay-precheck-sideeffects-independent/report.json、probe.py、source/replay原始物理表、session记录、SHA核对清单。脚本退出0只表示反例完成，case equal=false不能写通过；未将此探针当科学验证。
