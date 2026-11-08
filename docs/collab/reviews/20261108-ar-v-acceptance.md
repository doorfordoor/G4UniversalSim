# AR-V 验收工具修复签收

状态：**2026-11-08 当前主审已签收，AR-V 本轮约定范围完成。R2-05、R2-06、R2-07 关闭。**主审已核最终候选、原始报告与独立结论；无本切片阻断项。不代表 AR1、MR1 或全产品回归通过。

## 候选与实现

本切片遵循 [AR-V 合同](../decisions/20261108-ar-v-validation-slice.md)。主审冻结 10 个实现、回归与 CI 文件，清单及原始字节在 [集成候选](../../../out/collab/20261108-ar0-ar6/integrated-ar-v/freeze.json) 和同目录 `frozen/`。基线 HEAD 仍为 `25487eb13432c5f4e968aa405607056f6a8febce`，工作区有既有修改，HEAD 不代表本次未提交候选内容。

- R2-05：运行器在前置检查之前冻结开始身份，测试结束后采集结束身份；源码、测试、HEAD、backend/merge 二进制变化或采集失败均保留报告并非零退出。顶层身份取开始值，不再用结束源码背书开始时的二进制检查。
- R2-06：检查器对同一次读取的日志字节核 SHA 并解析唯一合法探针；单项和总数同步增大、日志不变仍被拒绝；缺失、非法和重复探针均拒绝。
- R2-07：关键检查改为显式条件及异常，普通、`-O` 和 `PYTHONOPTIMIZE=1` 下行为一致。计数、SHA、fail/skip、总和及基线限制仍生效。
- 集成：报告保持 v2，扩展为 `candidate_identity` v1；独立语义校验器接入正式 `--require-candidate-identity`。两套 CI 的全部七处门禁调用（含篡改负控）均要求身份；删除扩展无法通过正式入口。旧档案兼容模式明确显示 `legacy/unavailable`，有错误扩展时不得降级。
- 永久回归：保留原 237 个注册（含 AR1 事务用例），新增 `report_evidence_gate`、`validation_identity`、`validation_identity_contract`、`validation_gate_integration` 四项。后者真实调用 runner 生成报告，再分别变更副本，验证正式入口、旧档案入口与三种解释器模式。

## 验证与独立性

作者旧反例及自测分别保存在 `out/collab/20261108-ar0-ar6/author-ar-v-identity`、`author-ar-v-gate`、`author-ar-v-identity-contract`。它们不替代独立复验。

独立复验人 Dalton 不参与实现，仅在 [独立证据目录](../../../out/collab/20261108-ar0-ar6/independent/ar-v) 写入固定副本、人工反例、命令、退出码和原始日志；判定直接核输入与首尾身份，不以修后的门禁给自己证明正确。基础候选 126 次门禁与 6 组真实隔离 Git 身份实验已完成；最终集成候选另行绑定，未将旧候选结果改名为新候选结果。

主审最终集成：实际 runner 退出 0，6 项专项全部 pass，0 fail / 0 skip，共 1623 个断言入口；[原报告](../../../out/collab/20261108-ar0-ar6/integrated-ar-v/tests/20261108-202100-2ec575d3/report.json)、[严格门禁输出](../../../out/collab/20261108-ar0-ar6/integrated-ar-v/strict-gate.log)和[主审原始证据复核](../../../out/collab/20261108-ar0-ar6/integrated-ar-v/primary-raw-receipt.json)均保留。主审另直接重算六份日志 SHA、读取唯一探针、核首尾全字段与顶层开始身份，没有只依据门禁输出判定。身份用例 9/9，包括源码/测试/HEAD、两二进制替换、源码删除、二进制删除及两个正控；集成用例真实生成报告后执行 12 组×三模式共 36 次门禁调用。

本报告源码指纹为 `380b41ac0a65c3d538de3c08a76d7ce9cea64d61eb07059d6548a3d4fedf80db`，测试指纹为 `603ff7b6121e53659e22c0e971480946530d8dfc775ed450704028b03591a4d7`。`tracked_source_gate=fail` 如实保留，9 项未入索引文件包含本次新增文件、AR1 文件及既有协作工具；该专项未要求全仓跟踪门，不宣称全产品正式集成通过。10 文件冻结及逐字节核对承担本次有限工具切片身份。

最终独立复验：[完整报告](../../../out/collab/20261108-ar0-ar6/independent/ar-v/final-report.txt)结论为本轮约定范围通过、无候选阻断。最终候选真实被审 CLI 共 390 次：126 次门禁、6 组身份实验、258 次 strict/compat/helper 调用；59 个 exit0、328 个预期拒绝 exit1、3 个明确 legacy/unavailable 的 exit2，全部符合预期。独立[原证据复核](../../../out/collab/20261108-ar0-ar6/independent/ar-v/final-raw-observation-audit.json)共 3018 项、0 失败；此数不是作者断言次数。主审抽核 `-O` 下报告 8/日志 3 的拒绝及删除身份后即使加 triage/legacy 也拒绝的原输出，认可独审结论。运行会话全部结束，原失败和旧 403 记录保留。

据以上证据，当前主审对话 `01a1ba89-9372-73d2-8bdb-f253dd9d401f` 将三个问题关闭，并允许后续候选使用新正式门禁。最终冻结清单 SHA 为 `4af1af9a04aff912ca98c6b520fd18aebbc31cf59230078bbd426691aeba41d3`；签收基于明确的文件字节，而非未变化的基线 HEAD。

## 边界与接续

首尾内容快照不是执行目录锁定，不能检测两次观察之间变化后又恢复，也不是防任意篡改的签名系统。这里的临时原生程序只用于身份故障注入，不是 Geant4 模拟或物理验证。

本切片不改旧归档，不把没有扩展的旧报告补造成新协议证据。未运行云工作流、全产品矩阵、AR1 后端或新科学比较；CI 接线检查不能冒称云运行通过。未暂存或提交全仓文件，当前工作区源码跟踪缺口保留，后续正式产品候选仍须独立完成源码跟踪、构建与产物身份门禁。

通过后接续 AR1 的新候选构建、原生独验、box/tubs 和关联审计修复；MR1 仍只在 AR1–AR3 实质完成后由当前主审执行。MR2/MR3、DS/web 暂停和 F3 限制保持。其余 24 项正式问题及 3 项风险不会随本切片自动关闭。
