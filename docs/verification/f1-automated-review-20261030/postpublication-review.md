# F1 已发布自动归档独立核验

2026-10-30。结论：**批准本次已发布自动归档** `docs/verification/f1-automated-20261030`，未发现本范围的阻断缺陷。批准仅涉及自动证据归档完整性与既有自动门禁，不批准 F1 实窗验收关闭，不批准集成到 codex。

已测产品身份仍为 `f176d0ed4cea60b7ca5a80ed81017c9404ec1257`。后续仅文档提交不能替代这个构建身份。本次没有修改归档原件、被原 plan 选中的旧审查文件、helper、产品或测试；没有 UI、主构建或网络重跑。

## 字节与收据

除运行既有 `--verify-existing` 并确认退出 0 外，另用独立脚本直接遍历落盘文件计算 SHA-256/长度，不依赖工具的成功声明：

- manifest 的 **2797 个原件**逐项 SHA/size 全部与归档实际字节一致，也全部与仍保留的原 source 字节一致。
- **38 个 generated verification 文件**逐项 SHA/size 与 `archive-verification.json` 一致。
- `archive-complete.json` 的 manifest SHA 为 `a5d05c536c31899529cdc4a78d7738693dc1a0e326f3b4eb521e0e349d57ae8a`，verification SHA 为 `2ec541cceccd1ad1ba787616721d8a0cc8d257d5c575e5845ea3956621b4ae6a`；均与实际文件独立重算一致。
- 实际文件集合精确等于 2797 个 manifest 文件、38 个 generated 文件和 4 个归档生命周期/清单收据；无额外文件、缺失文件、大小写冲突或越界路径。

## 正式证据与历史分开

归档正式 release 集合恰好 **13 份报告**：Windows all 1 份、CI 12 份，全部严格门禁 0、逐例 pass/退出 0、非零断言、逐项与总数一致，并对应当前冻结 head/源码/测试指纹。

另有 **22 份历史报告**：历史 CI 20 份、历史 Windows 2 份；它们仍位于 history 路径、标为 retained history，不进入 release 集合。历史两轮 CI 保持 failed、分别 8/12 报告；历史中共 8 条失败用例执行记录仍保留，未被改绿。另 1 份 E6 报告属于 baseline，未冒充当前正式报告。

Windows 正式报告为 **143/143、48511 个 v3 入口**；E6 基线为 **134 项、42815 个 v3 入口**。独立逐用例比较确认原基线用例均保留且计数不下降；两个报告使用相同 `settrace_assert_lines_v3`，零断言列表为空。归档 baseline 比较收据为退出 0。

CI 独立核对：四个固定 artifact、十二组唯一 artifact/profile 和冻结 case 集合完全对应，总计 **414 条执行记录**。归档内两份原 workflow run 均为冻结 push head 的 completed/success：Linux run `41028779177`、M0 run `41028779326`；各自两个原 job 的名称/身份/成功终态、joblog 存在及原 artifact workflow_run/head 关联闭合。既有 `verify-existing` 又重验完整拓扑、逐例日志、严格报告门禁和 E6 baseline，未触发修改或发布。

## 阶段边界

当前已归档 README 明确写出“阶段未关闭”“实窗观察仍 pending”“尚未合入 codex”，并说明当前最终冻结尚无实窗截图、原生操作或 host 退出收据。真实小模拟与严格身份校验没有被称作实际窗口观察；**visible_acceptance=pending、phase_complete=false** 继续成立。

本独立报告作为发布后新收据留在 out，不追加进已经完成且按原清单固定的归档，不追改其 README 或旧 review。

复核产物位于 `out/collab/f1-automated-published-independent/`：

- `verify-existing.log`：既有归档工具的发布后门禁重验。
- `check-published.py`：独立字节、收据、分类、基线和原 CI 身份检查脚本。
- `independent-bytes-check.json` / `independent-bytes-check.log`：独立执行退出 0 的详细结论与哈希。
