# K2 正式验收：进行中

当前工程候选 `64bacb3e412ace7bf82fa9cf5969af679112c61b`，产品基线 `b1a7ffbc`，模板 `b2285d117a557614782eb8656593c2a64b9caba4538de91410126d7db35ba878` / 309成员。原候选4bc的失败保留。本页不是K2阶段关闭结论。

| 范围 | 当前结果 | 证据 |
|---|---|---|
| K2-3 独立工程双平台构建/运行/单行修改 | 已带非阻断限制签收，状态限制 | [独立工程验收](../../collab/decisions/20261107-k2-3-native-matrix-acceptance.md)、[原证据索引](../k2-build-20261107/README.md) |
| 两处正式阻断修复 | 已独审，定向通过；不代替正式矩阵 | [修复冻结](../../collab/decisions/20261107-k2-4-formal-repair-freeze.md)；out/collab/20261107-k2-final/independent/hb1310/ |
| 新快照/实际包内模板 | 980文件快照内309成员全SHA核对，真实构建器输出同一模板身份 | actual-snapshot-and-package-template.json；C实际64bac检出模板check通过 |
| 源码GUI/CLI真实入口 | 已独核限定观察：GUI生成项目317成员，CLI示例07为318成员；实际原目录全部字节/SHA及identity复算 | source-native-entry-check.json；作者observation-receipt.json与原始桥接记录 |
| 新desktop流水线，两平台 | success；167源文件集合/8份命令日志SHA独核，正常启动与ROOT读写exit0；旧目标及损坏导入预期exit1分别保留 | [run42376216450](https://github.com/doorfordoor/G4UniversalSim/actions/runs/42376216450)、repair-cloud/desktop-independent-check.json |
| 新Ubuntu正式static/gui | 2原报告严格通过：50+81用例、9220+11024断言，零失败零跳过 | [run42376216447](https://github.com/doorfordoor/G4UniversalSim/actions/runs/42376216447)、repair-cloud/ubuntu-formal-gates.json |
| 新Windows正式static/gui | 等待原任务结果 | 同一M0流水线，不重复触发 |
| 新Linux11.3.2/11.4.3后端正式矩阵 | 等待原任务结果 | [run42376216509](https://github.com/doorfordoor/G4UniversalSim/actions/runs/42376216509) |
| 新Windows/Linux安装验收 | 等待原任务结果；尚未签通过 | [run42376216446](https://github.com/doorfordoor/G4UniversalSim/actions/runs/42376216446) |

本轮详细证据根为 `out/collab/20261107-k2-final/`。作者交班原回执SHA256 `cfbdf1072eec68a6aa57120bd0c80f1fdd84e9d847a02274682da372af8e2da2`；作者turn133/134均已完成，终态seq75966，原会话idle。主审不重复派工。

源码GUI使用原4bc干净快照，运行时GUI代码及模板在64bac未变；不称64bac新程序构建。原第二次调用确实产出317成员工程，但关闭被未保存提示阻塞，主审核实其非正常退出与自有进程终止记录；第三次调用改用仅响应本应用关闭对话框的有界Discard响应器，实际桥接seq75786为actual_exit=0，两个自有PID随后均不存在。文件/命名/关闭对话框自动应答，不称人工操作或对话框视觉验收。

主审实际查看02/04图片：02能看到Export Geant4 project弹出项，但大部分背景被其它用户应用遮挡，不能宣称完整菜单/主窗可见；04显示真实Windows Run Console且没有启动后端。第三次不为美化截图重跑。截图仅保留内部证据，不作为公开产品展示。GUI原生平台windows，125%缩放；没有本轮Linux原生GUI导出动作观察。

本轮未直接操作安装版GUI导出动作：旧本机包早于该功能，当前云工件主要为日志/回执。安装版可用性仍需结合固定合同中的包内资源闭包、frozen运行与新安装流水线独审，不能将源码观察冒充安装版操作。此验证范围边界不引入额外打包/原生矩阵，最终签收结论待正式证据齐备。

原4bc：M0两平台及Linux两版本静态platform_paths失败；双平台安装build-runtime均因源码快照缺CMakePresets.json失败，旧Windows原任务现已终态failure。两平台原安装归档分别为SHA256 `062584e333926bf080fb468e33a3f79742cba0bb93ec6a083ea86679d7650ae8`（Windows）、`1aec6e3d8d588af662fa01db57af93f555615940cd0465eba0683135918183ce`（Linux）。不改写旧报告，不循环K2-3科学矩阵。F3及网页模型暂停保持原约束。
