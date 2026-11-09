# AR5 构建、独立工程与实际安装入口签收

2026-11-09，当前对话主审签收 AR5 约定范围。两轮联合审计 27 项正式问题至此逐项关闭；R2-R02 完成有界风险处置，保留无法证明排空时的阻断。验收范围为 CMake 源码所有权、安装/SDK、安装版 GUI 实际导出、仓库外 S-A/S-B、关联八项正式问题与一项 SDK 后代风险。最终云矩阵、最终生产与卸载是 AR6 的出口；累计 MR2 由主审另记。

## 候选与实际构建边界

- AR5 可追溯工作树以 AR4 提交 `998d8bf5cfdc37371efb01b2e0002d846be364e1` 为基线。Windows r2 生产冻结 SHA `bcb25d74c89bf96ee45f1277db2190e71d6f03243333bed0b1a8e230565f2d45`；Linux r3 为 `760e4ae34f83c8d084736e2b574375dd1d85c5c1c65710e6242eec13e55bc80f`。主审独立重算 1076 个生产成员及源码、测试身份；从 r2 到 r3 只变更 Linux 的打开目录实现、Linux 打包及共享打包 helper。后端原字节指纹 `0fe0fbea2088f665c3d10a1e1ccd56685a87df1ee132e44fcb03c3f341ae7ec4` 与 340 成员模板 `a7c474aaff090420a1e3de873db4e2b90adeaef3575e2ff64160b4c0bdc72013` 不变。Windows 同 r3 源受影响六项定向正式回归 6/6、5555 断言、strict stable；Windows 实际安装包仍标 r2，不冒称 r3 产物。最终生产另做同提交绑定。
- Windows/MSVC、Linux GCC/Geant4 11.3.2 和 Linux GCC/11.4.3 都有实际原生构建。三份 CMake File API 与实际链接图、Windows Ninja include 实录和反向依赖/环负控独立吻合。logic 不依赖 SDK；Geant4 实现依赖 logic/SDK；应用装配选唯一 GDML provider；GDML 两个 TU 的 native/stub 双编译是明示例外。头/源重建看实际依赖及重新计算的指纹。11.4.3 证据是原生组件/reader 范围，不替代新 Linux 11.3.2 可安装包。
- Windows 新 catalog `ad4cc913f8e93193c3b9970a6ed419a71d5ad70c5dd0f0b0ce2f6b11929722e0`，Linux 新 catalog `f3474fc3a3c8cdec6cc4013ece883295a1e0e1f3286e9b9572772008ef1cd3af`。均安装并公开 verify，SDK 与 runtime 分根。Windows 新 SDK 公共 consumer、application、恰两项无跳过组件均通过；Linux r2 SDK 同一 Release 二进制补真实 ENSDF 数据后两项通过，原缺数据失败保留。Linux r3 重用相同 SDK 归档，经安装核验并被本次两份实际导出真实使用。

## 两平台实际窗口及独立消费

- Linux 新包在私有 X11/xcb、无库路径覆盖下正常启动，进程映射核真实 XCB/EGL/GLX。两平台均由安装版 GUI 实际运行 O、复制重跑 C→E，各 20/20，从 C 直接打开 E 的结果及日志，并用应用内置 Python helper 合并 40 hits、20 event edep 行，原执行输出和输入 SHA 保持。Linux Trial 1 中主审保留 XDG 关联路径造成的 opener 失败；同包同 C 的 Trial 2 由发行版 Xfe 真实打开带空格路径，实际看到 E 的 stdout/stderr 和合并日志，正常关窗及退出。此为 X11 证据，原 WSLg RAIL 限制保留。
- Windows 本次 GUI、后端和两次内置 helper 正常退出。原收集器退出 1：为 41 个实际受观测进程读得 exit 0 后，尾查仅完成 21 个，20 个 CIM 查询超出总预算。保留原失败；独立的新完整进程表补证全部已退出且无应用写者，窗口布局唯一变更值恢复并读回，设置文件与恢复树见证保持。该补证不改写原收集器状态。
- Windows、Linux 分别从实际安装菜单导出 S-A 外部平行世界项目和 S-B 向导水靶。两平台 S-A payload `8d6d6fbe37eee2a8401120feb8193e31321ad75a39320a40def5116d85b3ca9f`（349 成员），S-B `e97c135c1434b40c3c926ed269546e1bfd0499f75d51480eb140b54571b6ec74`（348 成员）。主审对四次独立构建核七条命令退出、BuildInfo、原模板和全树一致、真实摘要逐 run，S-A 200/200（1 worker、seed 20261400），S-B 1000/1000（2 worker、seed 12345）；每份实际 CTest 恰 `h2_volume_scoring_check`、`parallel_scoring_component`、零 skip。真实依赖使用各自新装 SDK 和核验数据；没有从一平台复制原生包到另一平台。
- 单行开发路径：两平台分别在 S-A 独立副本中只增加 `summary.Set("k2_export_probe", "k2-controlled-change-v1");`，按各平台的已验 SDK 构建，实际完成 200 事件、真实摘要 marker 和新应用指纹；dose/fluence 各自前后逐字节相同，statistics 只排除冻结的两个时间列。Windows 两组件 PE 的 SHA 发生变化但未见新探针字面量；Linux 两组件实际重链接而 SHA 不变，实际符号表不包含改动的 FinalizeRunSummary。依据 [K2 实施冻结](../decisions/20261107-k2-implementation-freeze.md) 的实际依赖规则，主审核定 Linux 观察为正确的组件边界，保留旧合同字面观测不符，不更改源码制造组件变化。单行副本两平台也实际执行恰两项组件 CTest，无 skip；Linux 补验保原组件字节及原试次证据，JUnit SHA 为 `bcd8e6a99f1313abbedacbfb4c660022d54bfbe68bff06fe3c8c010f433d6caa`。该比较限定于既有 S-A，原科学适用域和 B/C、F3 判据不变。

## 审计原条款与证据

| 原条款 | 本次观察 |
| --- | --- |
| R1-AUD-04 | 实际矩形面源导出、Windows 和 Linux 各 200 个 primary 的工程边界读回；缺 shape、互斥字段、NBSP 反例保留，不扩大 K2 白名单。 |
| R1-AUD-05 | 首 section/注释、BOM 有无及 CRLF/LF 的真实 C++ 读取与导出一致；保配置原字节、重写结果及各自 SHA。Linux 11.3/11.4 与 Windows 独立 reader。 |
| R1-AUD-06 | 导出与真实 reader 对声明/引用大小写、冲突负控一致，保 NIST 名和合法旧入口，安装导出独立消费通过。 |
| R1-AUD-07 | POSIX 实际树外 manifest 链接在读取前拒绝，普通及 payload 链接对照；Windows 无文件 symlink 时仅记录该平台能力边界，保其他链接/文件类型对照。 |
| R1-AUD-14 | 实际 ext4 前缀执行位移除后字节 SHA 不变、公开核验按属性拒绝；恢复后通过。Linux 新归档与实际安装再验。 |
| R2-04 | 源码及冻结布局异根；两平台实际由 C 直接定位同一 E 日志、输出和两次 helper 合并，缺 Python/工具、已存在输出及坏来源负控按原状态保留。 |
| R2-08 | 隔离注入创建/写毕/发布间断，官方恢复仅认同事务；损坏、他事务及陌生文件拒绝，已发布内容未被覆盖。 |
| R2-09 | 实际 ext4 大小写敏感引用，错拼在规划时拒绝，正确配置可装/消费，Windows 对照单列。 |
| R2-R02 风险 | 实际 Windows Job/Linux 进程组受控父子测试，超时、正常退出、锁及下一阶段分别核证；无法证明尾部排空或已脱离组时保 guard 并拒绝后续，不宣称任意脱组可强制清理。 |

证据根位于本机项目 `out/collab/20261108-ar0-ar6`：`ar5-primary-close-r1/current-evidence-readback.json`、`audit-input-map.json`，Linux 菜单/实窗 `ar5-linux-r3-menu-consumption-prep-r1/EXECUTION-REVIEW.md`、`ar5-history-integration-r1/final-delivery-r1/linux-final-native-replay-r3/`，Windows 消费 `D:/Geant4/ar5-windows-r2-menu-consumption-prep-r1/REPORT.md`，实窗 `D:/Geant4/ar5-native-delivery-windows-final-r2/Native GUI Trial 2/Evidence`。旧失败、原应用和原用户项目保持各自身份。开发者入口见 [扩展组件、验证并继续开发独立工程](../../组件扩展与迁移.md)。
