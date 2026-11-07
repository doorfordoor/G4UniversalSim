# K2固定范围带限制验收关闭

2026-11-07。主审按[固定清单](../../collab/decisions/20261107-k2-closeout.md)及原冻结合同签收K2。工程/正式测试候选 `64bacb3e412ace7bf82fa9cf5969af679112c61b`，产品基线 `b1a7ffbc0519a29cb37b458e2e1542640956976a`，模板 `b2285d117a557614782eb8656593c2a64b9caba4538de91410126d7db35ba878` / 309成员 / 3820084规范字节。收尾文档提交不冒充新构建。

K2-1、K2-2、K2-4通过既定范围验收；K2-3状态为**限制**，其非阻断边界已由主审签收，不能写为普遍通过。仅S-A示例07与S-B向导单目标子集受验，不扩大高级物理能力，不称整个Roadmap完成。按[用户停点](../../collab/decisions/20261107-k2-stop-before-architecture-upgrade.md)，交班后暂停新增功能、后续派工及架构改造实施，等待整体架构优化计划与用户后续指示，不开L2。

## 正式验收证据

以下out路径均相对 `D:/Geant4/G4UniversalSim/out/collab/20261107-k2-final/`。

| 范围 | 结果 | 证据 |
|---|---|---|
| 合同及实现 | 有限消费者/闭包/失败事务独审冻结，r5/r6修复保留原反例 | [合同](../../collab/decisions/20261107-k2-contract-freeze.md)、[实现](../../collab/decisions/20261107-k2-implementation-freeze.md)、[正式修复冻结](../../collab/decisions/20261107-k2-4-formal-repair-freeze.md) |
| 独立工程 | Windows/MSVC与WSL2/Linux/GNU，两组件、S-A200/S-B1000、P7/P8、单行C++前后科学等价已独核，带限制签收 | [K2-3签收](../../collab/decisions/20261107-k2-3-native-matrix-acceptance.md)、[矩阵](../k2-build-20261107/README.md) |
| 正式报告 | **12原报告，734用例，376754断言，0失败0跳过，逐报告严格门禁通过** | hb1413/formal-12-report-gates.json |
| M0回归 | Windows/Ubuntu static+gui，success | [42376216447](https://github.com/doorfordoor/G4UniversalSim/actions/runs/42376216447) |
| Linux后端 | Geant4 11.3.2/11.4.3各static/gui/backend/integration，success | [42376216509](https://github.com/doorfordoor/G4UniversalSim/actions/runs/42376216509) |
| 冻结桌面 | 双平台success，167源码集合及8命令日志SHA独核，正常exit0与预期拒绝exit1分别保留 | [42376216450](https://github.com/doorfordoor/G4UniversalSim/actions/runs/42376216450)、repair-cloud/desktop-independent-check.json |
| 原生安装 | Windows/Linux 1.0.0、Geant4 11.4.3，runtime及SDK实际安装/使用/取消/重启检查/卸载通过 | [42376216446](https://github.com/doorfordoor/G4UniversalSim/actions/runs/42376216446)、hb1413/windows-installation-independent-audit.json与linux-installation-independent-audit.json |
| 必要真实入口 | 原4bc源码GUI生成项目317成员、CLI示例07为318成员，实际D盘原目录全部字节/SHA/identity独立复算，GUI实际正常关闭 | independent/hb1310/source-native-entry-check.json、作者observation-receipt.json与桥接seq75786 |

机器可读签收：hb1413/final-acceptance.json。四云均为64bac实际push运行；原4bc失败与K2-3科学/产物保持原SHA。作者原交班回执SHA256 cfbdf1072eec68a6aa57120bd0c80f1fdd84e9d847a02274682da372af8e2da2；turn133/134交班及135停点确认已终态，无须重复派工。

## 安装与交付身份

主审核对Windows9阶段日志/25归档证据SHA，Linux10阶段日志/23归档证据SHA。两平台均为980文件交付源快照，installed回执的309模板成员SHA/大小和模板manifest自身SHA均与b228一致；冻结GUI实际application_root与安装prefix一致，资源在该根export-template目录。

云运行时实际各完成5事件。Windows运行时/SDK分别验证48597/53438文件，Linux为48091/68788；SDK consumer及完整应用均完成configure/build/run。这些总文件数是云执行记录，主审未将所有远端文件再下载逐字节读取；独审覆盖保留的日志/回执、归档证据及309模板明细。

| 平台1.0.0 | runtime原生ZIP SHA256 | SDK原生ZIP SHA256 |
|---|---|---|
| Windows | 0d4e4975adff34a1d5998a290f65994d0bfe8971ea9d22a04292bc0e8c41adf5 | d9e028f5ab67ca99e00b778930fce615e423ae8dc9094e99c1db86b494f798f3 |
| Linux | 7f0967774eb5349b3517a85b950e4fafb79e8efb8bfdd33bef0d33c1cb667963 | fb97651ed9a1a152a73eccb0216b99f1b5b53453c8ab5d27426e066cbc275713 |

本地下载的是CI证据归档，不是上述可分发安装包；云执行器已清理自有包构建中间件。不能把证据ZIP称为已下载的正式安装包，整体软件发布交付仍属后续待办。

## 主审签收的边界与原失败

- K2-3的h2不链接被改文件，SHA不变；主程序/parallel及指纹确有变化。旧Windows97模块捕获退出null/unknown保持，44直接依赖与新进程exit0单列；PE跨构建可重复性、WSL2/裸机差异及旧argv身份记录限制见原签收。
- 本轮GUI实窗仅Windows源码入口；文件、命名、关闭对话框自动应答，不称人工对话框视觉验收。02图背景被另一用户应用遮挡，04显示真实Run Console且无后端运行；图片仅留内部证据，不作公开产品展示。
- 原第二次GUI调用被未保存关闭提示阻塞并由自有进程终止，原非正常退出保留。第三次仅对本应用临时项目使用有界Discard响应器，桥接actual_exit=0，两个自有PID随后不存在。
- **安装版GUI导出动作未直接操作，主审签收此观察范围限制**：固定清单要求的实际源码GUI/CLI入口、包内模板、frozen实际根、冻结源码及双平台安装已组合核对，满足原定范围；不得冒称直接安装版动作实测，不新增另一套整包/原生矩阵。
- C定向3550少两条文件symlink断言，junction实际执行；作者D3552单列。正式Linux导出3552及整体严格门禁通过，不伪写C3552。
- 原4bc平台路径检查及双平台安装缺CMakePresets失败全部保留。原Windows/Linux安装证据归档SHA256分别为062584e333926bf080fb468e33a3f79742cba0bb93ec6a083ea86679d7650ae8、1aec6e3d8d588af662fa01db57af93f555615940cd0465eba0683135918183ce。
- 主审本轮收据核验先后遇到原始/规范行尾和Windows git archive转换差异，改用git cat-file批读原始blob后分别核验；诊断hb1413/audit-normalization-diagnostic.json保留，未改产品或追加CI批次。

支持矩阵已在正式候选前更新为S-A/S-B有限支持，本轮复核事实一致，保持其受控字节及b228模板不变；阶段状态经其既有ROADMAP/CURRENT链接同步。源码构建说明/示例保持已验版本。F3噪声限制、Q2科学适用域及全部未验证范围不因K2关闭而改变。
