# Q2-4 统计不确定度预注册 v1

任务 ID：q2-uncertainty-preregister-v1-20261105。目标是把固定清单 Q2-4 化为可直接执行和复验的有限合同。**本轮只写方案、输入草案和纯数学核验，不编译或运行 Geant4。** 方案独立审定并冻结后才进入实验；不试跑挑种子。

前项结论：NIEL 表级审计已独立复验；27/0/3、17 项 Decimal 检查及 5 个反例已归档。结构/算术通过，物理评价 limited；不再补本项工具或材料。Q2-3 按已声明适用域限制签收。

## 输出与范围

- 只写 `out/collab/q2-uncertainty-proposal-v1/` 和 `docs/collab/outbox/20261105-q2-uncertainty-preregister-v1.md`。
- 交付 `proposal.json`、`cases.md`、`inputs/` 草案、纯数学核验程序和结果；明确每个输入/程序的 SHA、可执行命令、预期输出和缺行语义。JSON 标记 draft / execution_authorized=false。
- 只读现有产品、参考合同/数据、正式测试；不改冻结参考、数据表、生产入口、阶段文件或 Git。现有无关改动保持原样。
- 读 `docs/collab/reviews/20261105-q2-uncertainty-preregister-review.md`；边界依据实际 `HistoryStatistics.cc`、`DoseScorer.cc`、`LETScorer.cc`、`SensitiveDetector.cc`、运行输出生产者，而不是按希望补字段。

## 固定病例与预期

1. **UNC-TOT：事件内合并和零贡献**。沿用 REF-Dose 10 MeV 的嵌套硅几何/12×12 mm 束、EM option4 和 10 μm cut，单敏感体，N=20、threads=1、seed=20261120，启用 event_edep。将原始事件沉积合并后重算 S、S²、entries，并将未出现的已完成事件作为零贡献纳入 N；确认当前 event_edep 的原始单位/字段和单 SD 归属。用真实完成数及 generated_files 约束，文件丢失不能当零。
2. **UNC-N1：N<2**。Si 10×10×2 mm 敏感体内中心点源，10 MeV proton，沿 +z，EM option4/cut10 μm；N=1、threads=1、seed=20261121，Dose 和 proton LET。几何/点源预先保证进入敏感体；期待非零观测及 insufficient_events，不能把返回数值 0 当作有效零误差。若所选确定几何仍不满足，不更换种子掩盖。
3. **UNC-ZERO：无沉积及无选中粒子**。同几何/点源，geantino，N=100、threads=1、seed=20261122，Dose 与 proton LET。根据生产者判定哪些表可无行/哪些摘要仍应存在；DoseScorer 跳过零沉积、LET 筛选后可无行，禁止伪造 zero_total 或 undefined_ratio。完成事件/身份/失败状态仍须完整核对。
4. **UNC-LET-COV：比值相关矩**。沿用 REF-LET-v1 的 20 μm Si、100 MeV 点 proton、FTFP_BERT_EMZ、cut10 μm；N=2000、threads=1、seed=20261123。依据公开 A/B/C 及 BA/AC 交叉矩重算两种 LET 的 delta 误差，逐项明确公式与字段来源；不把未知协方差当零。只核统计恒等式，不再用旧 LET_d/LET_t 5% 外部物理门槛。
5. **UNC-MT-SPARSE：稀疏多线程**。同 UNC-N1 的几何/物理/源，N=2、threads=4、seed=20261124，Dose、proton LET 及必要 event_edep。N<线程数确保不能全部 worker 都有事件；按真实全局事件 ID/完整 N/metadata 与 worker 矩合并，禁止假定 worker0 获事件或所有 worker 输出非空文件；禁止平均各 worker 相对误差。Dose 原始事件和、LET 公共矩分别说明证据强度。
6. **UNC-COMPONENT：真实共享实现边界**。后续实施时用现有组件入口或最小一次性 C++ probe 直接调用真实 HistoryStatistics.cc，不能写 Python 镜像自证，不新增产品接口。预注册 fixture：N=0,num=1,total→insufficient；N=1,num=0,ratio,den=0→insufficient；N=2,num=1,ratio,den=0→undefined_ratio；N=2,num=0,total→zero_total；N=2,num=0,ratio,den=1→zero_total；N=2,num=1,total→approximate；N=2,num=1,ratio,den=1→approximate。相关矩 fixture：事件 A=[1,2,0], B=[2,1,0]，S_A=S_B=3、AA=BB=5、AB=4、ratio=1、R=sqrt(2)/3。有限性防护不是 UncertaintyStatus 自身职责，不扩大本轮范围。
7. **UNC-COVERAGE：独立有限批次**。沿用 REF-Fluence Galactic 10×10×0.1 mm 靶 / 12×12 mm 均匀方束和 geantino，fluence=true，hits=false，event_edep=false；M=64，N=2000，threads=1，seeds=220001…220064。不重采样、不延长批次；保留全部样本和 unavailable。一次真实执行失败保留原件并停止运行，不自动换种子重跑。

## 覆盖判据与纯数学交付

设计输入：`docs/collab/decisions/20261105-q2-uncertainty-coverage-design-v1.json`（只代表数学设计输入，未授权模拟）。自行用不同计算路径独立复算这些阈值，若不一致先报告，不改阈值迁就：

- p=25/36，测得 Fluence 的 ±2×报告标准误差区间，真期望总注量 N/144；R 使用项目原有未作 Bessel 修正的事件矩估计。
- 单批覆盖条件：`|K−Np| <= 2 sqrt(K−K²/N)`，覆盖 K=1347…1429；对应精确二项概率约 0.9559137115315595，不称通用 95% 区间。
- 64 批覆盖数至少 57；在该模型下低于 57 的概率约 0.006980515324（单项下尾 α=0.01）。总 K 的中央 99% 接受区间为 [88464,89313]。
- 两项检验各 1%，联合误拒绝率只声明上界 2%，不写联合 1%。冻结全部算法和比较边界，不能先看模拟后校准阈值。
- K 的推导用实际 entry/path 生产语义及直线路径恒等式；不靠 hits 全集假设。标明数量为总注量还是每事件归一化量，并在两个尺度下保持等价。

## 完成标准和停止条件

机器合同列输入身份、N/种子/线程、预期行存在性、每个原始量来源、比较公式/精度、反例、停止条件及结论适用域。CSV 的 12 位有效数字用事先固定的半单位区间传播，尤其 LET 消去项；不能统一改为 1e-12 相对门槛。范围至少包括误用 step 而非 event 矩、丢交叉矩、平均 worker 误差、遗漏零贡献/错误 N、缺声明文件，以及把 limited 当反例检出的负对照。

纯数学核验只针对分布/阈值，不借执行产品或观察样本选门槛。输入可静态生成；不得启动后端或新建通用验收工具。交付后停写待复核，回执给实际完成、文件 SHA、未决点和下一步复演命令；完整实现留下一任务。

你是本轮执行负责人，请有信心把这个高级科研项目做完整、清晰、美观、快速、易用。unlimited Token，不限子智能体数量，充分发挥设计和工程能力，充分实现与验证。实际平台限制以系统为准，不为消耗而重复工作。完成约定范围，范围外想法记入建议。
