# E4 规范与中文入门验收记录

2026-11-05。E4本轮固定范围验收完成并关闭，进入Q2。

## 候选与交付

文档候选f7793dcbc198f17e0bae935004df1d2a727a159e，云空间修复候选92b285d6d78ed3b887a7ee98ce8b5e4a6c0a0e61。应用产品864bc036，C++指纹e7de615d4e342114104f970688a7ea5f9789f7b70240b2562a388a50a45704e7。[身份映射](identity.json)记录对应关系。

E4交付46行事实映射、当前状态与能力入口校准、两平台中文首次运行/配置包导出说明、有效规则索引与历史迁移。README使用实际vs2026预设，配置包按K1导出与重新载入流程操作，WSL补充运行目录选择和失败恢复。生成矩阵段与原件一致，文档候选相对F2产品的应用源和测试字节已核对。

## 独立审查与复演

- [事实映射审查](../../collab/reviews/20261104-e4-map-review.md)核对46个唯一编号、实际文件和行号，修正旧基线及组合路径。
- [文档审查](../../collab/reviews/20261104-e4-docs-review.md)核对实际预设、导出入口、Linux启动命令、有效规则去向。两个AGENTS入口分别45129/47163字节，离开已观测的65536字节读取边界。182条实质删除行中181条在历史全文找到，余下一条F2日期标题更新后仍保留原实现约束。[逐行核查](local/rule-migration-independent.json)。
- [Windows/Linux复演](../e4-rehearsal-20261104/README.md)使用生产Qt动作、真实后端和屏蔽平板模板，各完成校验、100/100事件、读取新摘要、导出配置包、第二窗口导入。最终两次drained宿主均exit0，原运行表与manifest保留。
- 复演采用Qt offscreen，文件选择由驱动提供路径。安装版观察按已有I2正式证据及本轮云安装作业记录。原始WSL挂载目录Errno22、观察脚本取错属性及窗口未释放时的退出异常均保留原日志，正常退出结论绑定最终drained两次。
- 相对链接检查1369项、351个Markdown文件，零损坏。初稿1230项、修订1368项检查保留各自时点。

## 正式云测试

文档候选f7793dcb在Linux Geant411.3.2/11.4.3各static、GUI、backend、integration及M0双OS共12份原报告，708个用例、255154条断言。逐例非零断言、退出状态、日志原字节SHA及总量严格门禁通过。与F2总量相差9次的四处均来自两个会话测试的等待循环，测试指纹和用例集合相同，原始计数与定位见[计数对照](cloud/assertion-count-map.json)。[原报告门禁](cloud/strict-gates.json)、[4ZIP官方摘要对照](cloud/download-manifest.json)、[复制原件摘要](cloud/copy-manifest.json)。

[Linux双版本](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41860688390)、[M0双平台](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41860689162)报告均绑定原SHA。92b285d6只增加托管Ubuntu的云磁盘清理步骤及交付记录，安装测试步骤和应用字节按原候选映射。

## 云空间阻塞与修复

首次安装作业41860688699的Ubuntu磁盘预检差2059078146字节，原artifact13340360782已核验官方SHA与ZIP CRC并归档。[原失败与清理范围](../e4-rehearsal-20261104/ci/README.md)。

修复仅对GitHub托管Linux的固定预装Android SDK目录执行清理，测量安装工作区所在文件系统的可用字节。Ubuntu作业清理前89706803200字节、清理后101545197568字节，实际释放11838394368字节。Linux完整runtime/SDK安装均verified，10个阶段exit0且原日志SHA全部匹配。[Linux独立门禁](installation/linux/independent-gate.json)。Windows安装作业仍在运行，按附带CI事项持续跟进。本轮E4以文档候选f7793dcb的完整正式云矩阵、两平台复演及规范核查签收，剩余安装作业记录为主审已签收的非阻断限制。原空间门槛及应用输入输出定义按既有标准执行。

## 限制与后续

WSL挂载文件系统的发布限制保留，首次运行建议将runs root及包目标置于Linux自身文件系统。Qt动作复演与原生视觉、工程完成与科学基准各使用对应证据。已有J3主题切换性能及WSLg限制继续按原报告维护。

E4关闭后启动Q2，先建立量定义、独立参考和预注册病例，经独立复核冻结后运行科学比较。

## 阶段归属校准

Q1最终提交f25da40f明确将E4记为“部分完成，继续收尾”，当时已做部分规则迁移与链接校准。本轮完成后续J3/F2入口、实际构建预设和配置包操作说明的收尾。完整安装矩阵曾被扩大为E4前置，现恢复固定文档验收范围。附带Windows安装结果继续按92b285d6实际身份跟进，不改写为通过。
