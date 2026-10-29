# 完整 2C 最终跨作者只读审查

审查时工作区 HEAD：`d422e631bcbf2a9285a56914b00e9101da3945ff`，存在本阶段并行修改；行号为本次读取时点。仅改本审查记录，未修改产品代码、未启动后端构建或后端可执行程序。结论：发现 **1 项 P2 来源投影阻断**，待作者修正并补真实导出反例；不以本审查代替整阶段验收。

## P2：被忽略的空 em 仍覆盖 physics reference 的请求来源

位置：`src/Physics/PhysicsManager.cc:725`，共享实现 `include/Config/EffectiveConfigSupport.hh:43-44`；实际解析边界为 `src/Physics/PhysicsManager.cc:507-508`。

触发输入：

```ini
[physics]
reference = FTFP_BERT
em =
```

`LoadFromConfigImpl()` 对空白 em 明确不调用 SetEMOption，接受的 reference 仍由 reference 决定；但 ProjectEffectiveConfigFields 对 `/physics/reference` 无条件使用 `{reference, em}`，ConsumerState::Make 将最后存在的 em 声明写入 requested，并将它标为 accepted。结果空白且未参与覆盖的 em 被伪装成当前 reference 请求，来源链同时保留 reference 和空 em 为 accepted。该错误是本阶段核心“已接受来源链与消费者真实覆盖顺序一致”契约的违反，不影响该例实际物理列表选择，但会误导 GUI/差异审查和后续配置来源消费者。

独立复现：使用当前共享头、EffectiveConfig/IniReader/InputProvenance/StringUtils 编译，不依赖 Geant4；精确复用 PhysicsManager 投影调用：

```cpp
s.reader.LoadBytes("physics.ini", "[physics]\nreference=FTFP_BERT\nem=\n");
auto f = s.Make("/physics/reference", "FTFP_BERT", "", "physics", {"reference", "em"});
```

落盘证据 `out/collab/final-cross-probe/probe.cc`、`build.log`、`result.log`。当前输出：

```text
requested="" resolved="FTFP_BERT"
::shadowed
reference:FTFP_BERT:accepted
em::accepted
```

这是共享组件实测加真实调用点/解析点对照，**没有宣称完整后端已复现**。修复须按真实非空 EM 参与规则投影，保留被忽略空声明的诚实说明，不能改变旧解析语义；补 `--dump-effective-config` 的空/空白 em 与非空 em 正反例，核对 requested、accepted/shadowed 和 resolved。

## 已覆盖范围及证据边界

- SourceManager：模式适用字段、单能/分布分支、具名身份、preset 来源、谱与相空间输入。谱由一次 ReadFile 的 bytes 解析并保留同份 SHA，PhaseSpace 亦从捕获 bytes 流解析，未见导出重开文件取哈希路径。Source 加载仅在实现成功返回后 Accept；未把缓存值当 GPS 读回。
- PhysicsManager：reference/manual 分支、EM 与模块选择、cuts/region、运行时构造器 inventory 的保守 unknown；发现上述空 em 投影问题。失败配置前已有 Manager 内部赋值的路径存在，但本次未据此声称可观察的拒绝事务发布污染，未作为未经复现的问题上报。
- FieldConfig：candidate 加载后交换发布、场图同字节输入、局部对象/单位投影及 module gate；未发现确定 P1/P2。此结论为只读审查，不是场图运行或轨迹验收。
- GeometryManager：独立 reader/input 捕获、模板树成功解析/校验后发布、JSON Pointer 身份和派生字段来源；GDML 导入占位字段未冒充实际尺寸；未发现本次可确定的 P1/P2。同字节外部资源捕获仍需正式 GDML/STL 真实专项证据。
- MaterialManager/MaterialIniReader：candidate 从捕获 bytes 解析，成功加载才加入 inputReaders 并 Accept；部分 BuildAll 失败记录 incomplete/failed，不宣称完整回滚真实 G4 对象。已读定义/别名/NIST 投影，未发现可复现的新阻断。
- ConsumerState：已检查 requested 缺失保留、成功命令重投影、generation 与收据解析值 SHA 绑定；上述忽略值参与来源问题定位到具体 Physics 调用，未提出全局盲改多个贡献键语义。
- EffectiveReceiptView：检查 thread/run/generation/resolved SHA 作用域、未知命令降级、不同绑定失败隔离及 immutable annotation。运行 `python -B scripts/test_effective_lifecycle.py --component` 返回 0，输出 PASS independent receipt reducer/target failure isolation/generation/run scopes/immutable snapshots/read-only classification。该组件测试不启动后端，不证明实际 worker 收据生产完整。

本记录仅报告上述确定 P2，无优化建议清单。最终冻结需主任务确认修复与本轮真实专项、完整平台和 CI 证据；独立组件通过不提升为完整 2C 完成。
