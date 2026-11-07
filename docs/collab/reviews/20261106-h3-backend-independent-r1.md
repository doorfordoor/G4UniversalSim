# H3-2 首次实现独立审查

日期 2026-11-06。结论为失败，需在原 H3-2 范围内修复。交付源码补丁 SHA 与作者回执一致，现有两个专项曾复跑通过。本次新增检查发现下列冻结要求尚缺实现。

## 必修范围

1. `ParallelWorldConfig.cc:252–444` 只检查声明 section 名称，没有校验展开后的名称冲突与不同计分盒交叠。`Slab` 与同位置的 `Overlap` 可同时进入已接受配置。`SlabGrid` 的派生单元与显式 `[volume.SlabGrid_0_0_0]` 也可同名。需统一验证声明/派生名称、路径安全、盒内部交叠，允许仅面/边/点接触。`AppendVolume:444` 只 push，4096 仅每个 grid 检查，总数未限制。
2. `ParallelWorldConfig.cc:527–568` 把含有异材料 daughter 的水母盒视为整个平行盒材料一致，且 ContainsBox 直接使用局部 position，忽略祖先位移和旋转。需保守证明整个区域的实际材料一致。无法证明时输出合同规定的 unknown，避免错误 true。可以先支持可证明的轴对齐叶盒，其余 unknown。材料别名应比较解析后的实际材料身份。
3. `ParallelWorldConfig.cc:536–539` 未在构造前检查参考质量及总质量有限、正值，派生中心与边界算术也缺有限检查。需在创建内核几何前拒绝非有限/上下溢结果。
4. `EffectiveSimulation.cc:135–165,226–231` 没有接入 parallel config 的 Accept、字段或证据汇总。新增类的相关方法未被消费者调用，不能证明回执声称的三级证据链。`FinalizeRunSummary` 还将全部 run 完成事件数配最后一个 runID，output SHA 为空。需接入既有机制，按真实 run 与实际已完成输出记录。未启用时保持旧快照语义。
5. `ValidateDependencies` 只在 Configure 执行，batch macro 后续可改变 biasing/scoring/output 或创建原生 mesh。初始化后的 `ValidateParallelWorldForRun` 只查几何，没有重新核验当前依赖。需覆盖配置完成后的实际受支持入口，在物理/SD 构造与 BeamOn 前拒绝合同禁止组合，保存失败摘要和非零退出。重点反例为预初始化 macro 启用 biasing，以及 native /score mesh。

## 证据与边界

源码初版快照和 SHA 位于 `out/collab/h3-independent-r1/source-r1/` 与 `source-r1-sha256.json`。复现输入、原失败日志位于同目录 runtime-attempts 与 overlap-precreated-output。双盒交叠输入已到达 dry-run completed，但最终摘要文件写入因 Access is denied 失败。该退出码 1 属输出环境失败，不能记为配置拒绝，也不能记为完整运行成功。作者原构建 SHA 为 9ffb2d02035251cc32e5add90ad173197d90fd5189490b78bdfae19d8076f37d。

原 DSH round113/turn96 completed 已从原任务核实，回执 terminal seq56861，已处理至56863。桥接恢复的监听进程为18264，自动脚本的 CommandLine 过滤没识别该进程，先前 host 未运行判断需更正为端口发现失败。

修复停止条件为上述五组原要求接线与聚焦回归通过，交付新身份等待独审。不新增框架，不进入 H3-3/4，不改物理判据。辅助网页模型的只读复核另记其审查文件，主审负责合并确认。

## 后续原版负例复演

独立网页任务使用固定9ffb2d02程序复演3例，均exit0且status=dry_run。主审读回完整stdout/stderr与摘要，分别证实完全交叠、派生重名、总8192单元的输入被接纳。证据为out/collab/h3-independent-r1/web-runtime/results.json与supervisor-verified.json。此前主审通道Access is denied原失败保留，可用独立任务通道继续运行复验。
