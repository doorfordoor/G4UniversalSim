# E6 独立交付只读复核（2026-10-30）

## 结论
未发现阻止实窗通过后正常集成的 Git 或冻结身份问题。实窗由主负责人/其他审查者进行，本复核没有操作 Windows UI，不宣称其实窗通过。没有重跑134项，没有修改产品或正式文档，没有网络推送。

## 当前事实与身份
- 阶段工作区 HEAD 838e2e366f433037f85b07cd6cfb7c76ba87b6fe，roadmap/E6-config-compat；两次 porcelain 无输出，clean。
- q1-final 工作区 HEAD c6bf8ad2c4d58b5e66392b1a029859c26b6dc17a，codex，porcelain 无输出，clean。
- git merge-base --is-ancestor c6bf8ad HEAD 返回0，允许在最终复核后正常 fast-forward。缓存远端 origin/codex=c6bf8ad、origin/roadmap/E6-config-compat=838e2e3；本复核未 fetch，不能据此声称服务器当前未变化。集成前应再检查远端/并发状态。
- 原 D:/Geant4/G4UniversalSim 是 roadmap/F6-live-progress、5465dbd，不是此次集成目标；未修改。
- a779634 到838e2e3仅文档/证据路径变化；排除docs、STATUS、CHANGELOG后差异名单为空。
- 实时计算源码指纹 ab79c6c2227518bd7f38d5109998ed0998d8fd53ad500cfbe714d544eb19a474、测试内容指纹 e9b4f852e36dca85971d40da2c63ed6fd184055358ca965116babba6b16fafd4，均精确匹配冻结 Windows final-1/report.json。
- 实时exe SHA256 09dd7521be81f21c1c2a6f1b751eb1c6b171c70c4b206814a821b3e8b73aa3a5，匹配归档 additional-files/1-e6-repair-build-identity.json 与实窗准备记录。正式Windows报告 provenance=source_sha256_manifest_matches_executable，Release/MSVC19.51.36246.0/Geant4 1132/MT。未把Linux11.4 CI变成Windows11.4验证。
- 实窗准备manifest列明13个源码当前实际SHA全匹配（0 mismatch）；准备状态本身仍不是执行证据。
- 当前acceptance-state.json仍stage_complete=false，visible pending，merged_to_integration=false；此时正确。

## 实窗通过后的最小正式更新
1. 新增独立可见验收目录（建议docs/verification/e6-visible-20261030），归档实际操作/程序化与观察区别、截图观察、报告/日志、源码测试exe身份和未覆盖范围。记录迁移预览/取消/目标冲突与源字节保护、snapshot当前输入与提示、Duplicate&Run副本线程/seed/name及最终摘要。不能把已准备/已解锁等同通过。
2. 更新STATUS.md E6标题/段落与当前顺序，docs/ROADMAP.md E6行及交付日志，docs/collab/ASTRA-BRIEF.md优先当前交接，CHANGELOG.md E6标题/首段，docs/配置兼容与迁移.md末尾自动验收状态句；各处链接新实窗证据并保留a779634/CI身份与限制。
3. docs/agent-history.md追加新实窗/阶段关闭条目，保留已有历史待验条目原意。docs/collab/inbox/20261029-2355-astra-e6-execution.md可以追加最终检查点，但不是必须改写的历史文本。
4. acceptance-state.json不在2711文件manifest清单内，可在证据通过后更新visible_acceptance/stage_acceptance/stage_complete并链接新实窗收据。merged_to_integration仅在实际合入后改true，记录确切实现/证据/集成SHA；不要提前承诺。若避免追改既有状态，则另建final acceptance状态并在状态入口明确指向它。
5. 关键：旧docs/verification/e6-full-20261030/README.md在2711文件manifest中（active_index），不得为去掉“待验”而覆盖，否则破坏原字节审计。保留历史README及原Windows/CI报告/manifest，当前导航改为新实窗/最终交付入口即可。新增正式证据应有独立清单，不重写原2711清单。
6. 功能支持矩阵的生成表无新功能变化，不需机械改写；若要更新“E6候选”导航，仅改人类状态段，不能手改生成表。文档更新仅做相关链接/状态静态检查，不重跑已冻结全量。

## 正常集成与范围
仓库ROADMAP提交节点允许整项独立复核后正常合并/快进及既有授权范围内普通推送，不要求每子提交再次批准。实窗通过后先提交新验收证据/关闭文档，重新核对两个工作区HEAD/clean与远端并发，再在q1-final/codex正常ff-only；不能reset/强推或触碰原DSH工作区。若远端有分叉，先审查差异，不假设本次本地拓扑仍有效。关闭提交与主线集成是不同事实，真实合入后登记合入收据与推送结果。

下一完整代号是F1；默认顺序F1→F4→F5→K1，I1只读环境设计可并行。用户一次启动一个完整代号，不因E6完成自动宣布F1/Q2/J2/K1/I2完成，也不擅自开始后续阶段。

## 必须保留的风险/证据边界
Linux8报告git_dirty=true，指纹内身份有证据，完整dirty集合未采集，不能改称整检出clean或断言仅依赖生成物。工程验收不增加物理正确性证明；394schema不等于GUI全编辑。迁移格式检查、标准快照恢复、标准包duplicate的已知边界与K1/J2/Q2后续职责保留。旧冻结README的pending是当时状态，应由新证据解释，不应为当前宣传破坏历史字节。
