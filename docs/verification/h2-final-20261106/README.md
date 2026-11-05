# H2 固定范围最终验收（2026-11-06）

结论：H2-1..5 固定范围独立验收完成，进入 H3 平行世界计分。

## 冻结身份与工程证据
产品/测试候选 5f68ede07b7da4fa673eafd38532694efdb9c4b0。后续阶段记录为 docs-only，不冒充新构建。
四个真实云工作流全部 success，见 ci-runs-final.json。M0 双平台、Linux Geant4 11.3.2/11.4.3 的 12 份原始报告均经独立严格门禁通过，共720用例、357003断言入口，无失败/跳过。见 cloud-independent-gates.json。六个测试/安装 ZIP 按 GitHub SHA-256 和 CRC 验证，另两份桌面 ZIP 在先前核验，见 final-artifacts-verified.json、desktop-verified.json。大件原件保留 D:/Geant4/G4UniversalSim/out/collab/h2-final-r2-cloud，并非全部上传公共Git。
双平台安装 runtime/sdk flow=verified，Windows 9/Linux 10阶段日志原始哈希一致，runtime各实际完成5事件，见 installation-independent.json。平台安装包分别命名，版本均1.0.0，Geant4 11.4.3。
C盘独立 Windows 11.3.2 新候选编译、3用例463断言及严格门禁通过；无变化测试复用首候选限定证据。独立实际收据 Dose 114/5/109、Fluence 614/505/109。Windows原生过滤/能谱前置校验、启用后恢复与退出0，见 native-observation.md。Linux云GUI为offscreen，不称本阶段Linux逐页原生视觉验收。

## 固定清单
|项|状态|证据|
|---|---|---|
|H2-1|通过|合同r1与20261106-h2-contract-freeze.md共同冻结|
|H2-2|通过|体积/网格过滤与按体积谱，组件和实际运行、正式回归|
|H2-3|通过|配置/schema/GUI111断言、示例与原生操作|
|H2-4|通过|独立分量和、谱和、边界/权重/事件N、DDD算术及V7批处理/csh/session零事件拒绝；合法会话V5完成100事件、唯一非零bin5=1 mm^-2|
|H2-5|通过|上述正式矩阵、真实云、原件严格门禁、安装、文档与集成交班|

## 失败历史与适用边界
首候选a434a9d9 Linux GCC整数构造歧义与schema生成失败保持原失败，5f68ede0仅最小修复类型及生成矩阵。原V7 worker拒绝前发生10事件及session绕过发生1事件的失败保留，修复后独立各入口0事件拒绝。V5首次会话夹具相对路径未启动，绝对路径复演通过，不能改写首次结果。
H2有限基准不扩大Q2科学适用域，原factor10、强子LET、DDD逐步、NIEL物理评价限制继续保留。普通中英文提示与窄区横滚为后续改善。

详细独审见 ../../collab/reviews/20261106-h2-v7-session-independent.md、../../collab/reviews/20261106-h2-v7-independent-r1.md；原始基准 out/collab/h2-benchmarks、h2-v7-independent-r2。下一阶段按H3固定清单执行。
