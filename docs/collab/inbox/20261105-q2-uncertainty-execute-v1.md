# Q2-4 冻结统计实验实施 v1

任务 ID：q2-uncertainty-execute-v1-20261105。预注册 R1 已独立通过，现在完成固定 Q2-4 的实现、自测和交付，不再停在计划。

## 合同与范围

- 读取 `docs/collab/decisions/20261105-q2-uncertainty-freeze-v1.json`，SHA-256 `5768cc413d7e05b586fdbe8074342e52ec14cdbf27fbc037163604775e0381b6`；以该冻结合同为准。源方案 `out/collab/q2-uncertainty-proposal-v1/proposal.json` 保持原 draft 字节，不改既有预注册目录。
- 只写 `out/collab/q2-uncertainty-v1/**` 和 `docs/collab/outbox/20261105-q2-uncertainty-v1.md`。不改产品、正式测试/基准/构建、冻结合同、表数据或阶段文件，不提交 Git。
- 后端使用已有 `out/collab/q2-backend-864bc036/G4UniversalSim.exe`，SHA `f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f`，Geant4 11.3.2。先核身份/数据集 required_complete，不另建后端。
- 将预注册 `inputs/` 的 17 个文件逐字节复制到本任务 inputs，按 manifest 验证。保留原输入；路径搬移仅允许冻结规则列出的资源/输出绝对路径重绑并同时记录原/新 SHA，不改变科学参数。

## 实际执行

1. 写最小输入检查/串行运行器、比较器和反例脚本，复用已有输出/身份语义；不造通用测试框架。记录 argv、工作目录、环境中的非敏感数据路径、开始/结束、退出码及原始日志，覆盖 seed CLI override 的实际生效值。
2. 按合同执行 UNC-TOT、N1、ZERO、LET-COV、MT-SPARSE 共 5 次后端运行；再执行 64 个固定覆盖批次，共 **69 次后端运行、130123 个计划事件**。覆盖批次 seeds=220001…220064、N=2000，不增加批次或改变门槛。
3. UNC-COMPONENT 用候选目录内一次性 C++ probe 直接编译/链接真实 `src/Scoring/HistoryStatistics.cc`，核对冻结的三个生产源 SHA，执行 7 个状态 fixture、相关矩及可区分的合并/错误平均 fixture；记录编译命令/源码/产物身份。不是 Python 镜像，也不另建产品接口。可复用现有 MSVC/CMake 环境，只修到此次编译能完成，不改系统权限或安装环境。
4. 对每次运行核 run_summary 的真实状态/完成 N、metadata 的 run/worker/产物 SHA；逐事件沉积、每 worker 计分矩、master 统计分别按合同复算。已完整完成且身份匹配的运行，在修比较器后复用原件；不要因报告或分析脚本变化重新模拟。

## 关键判定提醒

- 保留 R1 修正：12 位有效数字量级半单位（尾零省略不放宽）；LET_d 的 C²/B² 分母顺序；完整 event_edep 行数就是 N；不能用非零 entries/hits 行数替代 N；weighted_edep 可直接与 weighted dose 对账。
- N=1 的 `insufficient_events` 不等于 R 数值必须精确为 0。全零病例应是 Dose/LET 已登记的表头文件及无 scorer_statistics；不造零误差行。
- 稀疏 MT 依实际分配汇总所有第一/第二/交叉矩，不要求 worker0 得事件、不要求每 worker 非空，也不要求错误平均在这次分配中必定与合并值不同。可区分反例使用事先指定的组件/副本 fixture，不能换种子。
- 路径矩与注量矩区别：L=0.1K、L2=0.01K（mm/mm²）；V=10 mm³，注量 S=0.01K、S2=0.0001K（mm⁻²/mm⁻⁴）。读真实列名，不把路径的 sum_sq 当统计注量的 sum_sq。
- **每个覆盖批次不一定覆盖真值**。正常未覆盖记 uncovered，不能据此停止或换种子；64 批结束按 C≥57、总 K∈[88464,89313] 两项冻结判据判断。结果限于此分布/输入，不称普适置信覆盖。
- 真实执行失败/证据缺失保留原件、停止后续运行并报告最小定位；不得重采样、挑种子、改变 N/cut/几何/公式门槛。比较器自身 bug 可就地修正后重读同一原始输出，首次失败保留。

## 交付与停止

输出 README、机器 results/identity、全部原始输入/输出/运行收据、真实 C++ probe、比较器、8 类冻结负对照及其目标 fail id。反例只改副本，基线与原件 SHA 前后核对；baseline 的 failed/limited 不能充当检出。真实分配不具可区分性时用明确 fixture，不制造虚假 pass。

自测完成写回执：实际运行数/计划与完成事件、通过/失败/限制、失败首因、SHA、原件位置及精确复演命令。执行完成只表示待独立复验，不改 Q2/阶段状态。整项交付后停写待复核；范围外改进记建议，不执行。

你是本轮执行负责人，请有信心把这个高级科研项目做完整、清晰、美观、快速、易用。unlimited Token，不限子智能体数量，充分发挥设计和工程能力，充分实现与验证。实际平台限制以系统为准，不为消耗而重复工作。完成约定范围，范围外想法记入建议。
