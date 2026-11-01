# I2/J1 自动测试与交付原件归档

六个不可回填的增量保留35份报告（包含专项与历史失败）：32份严格通过，3份保持严格失败。最终阶段采用的报告与提交由[最终验收状态](../acceptance-state.json)明确选择；归档完整性通过不能把旧失败变成通过。

最终M0为6310969 / run41317395299：Windows static44/3959、GUI59/6739，Linux static44/3966、GUI59/6739，四份原报告与日志均严格通过。03d2c48的Linux双版本、desktop和full-installation工作流分别为41314991413、41314991520、41314991412，均实际成功；原03d Windows M0失败保留。产品文件未改的对应关系见[身份映射](../identity/identity-map.json)。

本机最终Win114 integration是03d2c48的29/29、6045入口；5fe原114缺Xerces helper的失败不改写。独立helper只验证原生Xerces组件，应用GDML OFF保持。两平台安装runtime各5/5事件、SDK consumer及完整源码构建/能力查询、取消/恢复/核验/卸载有原始收据与构建日志。

## 索引

- `increments.json`：增量目录与manifest/ZIP原SHA。每个增量含不可回填的manifest、内容对象ZIP、strict-gates和遗漏清单。
- `reports-index.json`：报告原来源、HEAD、dirty状态、profile/专项范围和strict结果。
- `delivery-index.json`：安装/获取收据导航，仅为派生索引；判断依据仍是ZIP中的原件。
- `external-original-artifacts.json`：官方原ZIP的本机位置、大小、GitHub digest及实算SHA。原ZIP没有全量重复入Git，也没有声称永久公开。
- `package-manifest.json`：本目录文件封条，不自包含它自己的SHA。

## 脱离原始目录复验

复制本目录后，使用Python标准库执行：

```powershell
python verify_archive.py --replay-dir C:/review/i2-j1-replay
```

目标必须是新目录。工具核对每个ZIP/对象/逻辑条目，重建报告与日志，使用归档的原strict checker；只在内存映射跨OS日志位置，原报告字节、HEAD、测试指纹与SHA不变。旧失败仍应得到strict fail；与manifest一致时，归档复验本身退出0。不会读取原out目录的日志或原GitHub ZIP，也不会重新模拟、安装或下载。可加`--extract-prefix delivery/`导出已选交付原件。

## 保存范围

已选报告包含其引用的全部逐项日志；CI run/job/attempt/artifact身份、冻结源/产物索引、ROOT自检、安装生命周期、SDK consumer与应用构建日志、host工具身份、官方获取MD5/SHA语义和许可索引均按实际原件保存。

没有复制SDK、数据集、冻结二进制或完整运行树；部分重复计划/小ROOT仅以SHA和理由列入遗漏清单，许可索引不冒充全部许可正文。大CSV在native包另记原路径/大小/SHA。历史失败与最终成功共同保留，必要判断证据可按本目录独立复验，不能因此宣称所有原始大工件已完整归档。