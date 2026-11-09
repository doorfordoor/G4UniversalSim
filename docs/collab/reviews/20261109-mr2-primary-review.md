# MR2：当前主审的前后端与交付累计复查

2026-11-09，当前对话在 [AR4](20261109-ar4-acceptance.md) 和 [AR5](20261109-ar5-acceptance.md) 各自独立验收后，复核 [MR1](20261109-mr1-primary-review.md) 之后的编辑、运行和交付整条链。结论：**MR2 通过，准许冻结 AR6 最终候选。** 正式云矩阵、最终提交的双平台新安装包、实装入口和卸载尚须按 AR6 完成；本记录不签 MR3。

| 累计边界 | 本对话直接核验及裁定 |
| --- | --- |
| 编辑→保存/生成/导入 | 当前 `WorkspaceSnapshot` 在所有权边界复制 project/state，持久化时仅一份编辑态，临时读源事实不进入持久 codec。EditSession 的事务、Undo/Redo 与 run/path、SPS、材料/几何动作的写入方向一致；窗口仍负责采集用户动作和投影。保存捕获 session，不能从控件回写未接受草稿。对照 AR4 r3 真实 source reload、失败保留旧值与 raw 草稿、SaveAs/reopen，以及当前 generated 修复：安装版 O 实际通过，旧 source-package 变化误 stale 的负例保留。D07 的有限例外仍有效：纯动作不用创建 QWidget/QApplication，现有 i18n 传递导入 PySide6；不宣称完全无 Qt 依赖。 |
| 生成/外部输入→运行 | 两种输入均通过实际 source/package validation、frozen revision 和运行服务进入后端。当前 `ExperimentWorkflow._finish` 持久化最终状态；落盘期间到达取消/编辑先重发终态，copy locator 只在 publication fence 后发布。没有从可见进度或单一 exit 0 推断通过。AR-V 计数、-O、防漂移门未变；AR5 runner diff 只增加三个用例及候选探针的绝对 exe 路径和真实源码指纹接线。 |
| 扫描/历史→分析/导图 | 对照 AR4 同集合乱序及缺项、双 run overlay、单格非零中心、named source/physical field 的有限正反例；图与 CSV 由同一已选 run、series/volume 及物理范围消费。当前 History 复查同根旧包与明确 C→E 两路：locator 只保存 ID，受路径/回执/原 snapshot 哈希约束；打开时重验已选绑定。成功仍由 fresh summary、过程回执及相同 execution id/metadata 验证，污染输入不会退回旧成功。两平台实际 20/20 重跑，C 直达 E 的 logs/Results 及两次合并已复核。图表历史检查沿原候选引用，不把实窗菜单试次说成新全量图表回归。 |
| 分发→独立开发 | 独立目标源码、三份 File API 与源码包含/依赖例外保持。复核两实际菜单模式、真实不同安装根、逐 run 和 JUnit；四份消费的 28 个已等待命令 exit 0，四份各 2 测试，0 skip。Windows r2 到 Linux r3 的原字节差异仅三处平台打包/目录入口，后端与 340 成员模板不变；两份 standalone payload 各跨平台一致但原归档与 SDK 绑定分别登记。单行新应用与原科学 CSV 对照成立；Linux 无依赖组件哈希不变的裁定见 AR5。 |
| 原问题和风险 | 主审以总规划原 ID 作精确集合：第一轮 16、第二轮 11，19 个先前签收逐一找回，余 8 个由 AR5 原始证据签收，第二轮内部别名不重复计。风险 R1-R-02-B4、R2-R01、R2-R02 均有各自实证及限制，未改列为一般缺陷。SDK 无法证明已排空时保阻断；没有把原 Linux opener、Windows 原收集器尾查失败或原缺数据的 CTest 改称通过。 |

AR6 只冻结本隔离工作树中已授权的产品、测试和文档，原工作区的两份用户暂存 blob 原值保留且排除。最终身份按 Git 提交、tree、checkout 原字节、构建 raw 指纹、测试指纹、模板、安装包及报告分开登记；Windows/Linux 换行归一有单独映射。私有候选分支触发现有四个 workflow、计划 8 个 job 和 12 份严格 profiles；本地双平台新包、真实安装入口、仓库外消费、受控扩展路径、正常卸载与源码依赖说明分别保留证据。未达项不得由旧候选替代。

保留 MR1 的科学裁定与限定域：AR2 的 H2/H3 原执行与独立分析仍按原身份；AR5 改动落在 INI/别名、构建链接和交付，没有新增 scorer 路由、分母、过滤、步或随机抽样变更。AR6 仍须按实际最终差异做原有限迁移对照与正式 profiles，不能用 S-A 的对照外推其他物理量；不启动额外 H3 B/C 或 F3 批次，不更改原失败、置信门槛或 GU 的用户验证要求。

主审机器回读：本机 `out/collab/20261108-ar0-ar6/ar5-primary-close-r1/{mr2-main-inputs,current-evidence-readback,audit-input-map}.json`。运行原件的目录与身份见 [AR5 签收](20261109-ar5-acceptance.md)；[AR0 r3 冻结合同](../decisions/20261108-ar0-r3-expanded-contract.md)保留原字节。
