# F3-1 独立复核与冻结决定

2026-11-07。状态：通过。作者round149/turn117 completed/idle已核；主审独立核对四文件SHA、JSON交叉哈希及4种输入AST原表达式渲染，通过后冻结F3-1。固定清单不扩项，本决定与作者v1-r1合同/输入参数共同构成冻结协议；冲突以本决定为准。原首稿953ff539及其失败保留。全部条款在性能/模拟结果产生前写定。

## 身份与固定矩阵

基线代码f812465bbfd58026201b70a23938e6bdc8ea12eb，canonical指纹fc498cc7f261b89d39558218668cb197bcaa3a94ff0c661f0b7f8fd2dab822ec；exe SHA2ff536c552c6315eb33737b6c0f926a589f62b57df0a6271e39db0a0b3969a0d。D旧构建及三旧H2换行映射保持，不规范化或重建冒身份。现有脚本bba050e2、几何22cf29b2及四输入模板沿用原字节。

参数维持1000事件、2线程、seed4242，hits/mesh×csv/root；F3-2一次4例warmup、20计时、12独立内存；F3-3一次8例warmup、40配对计时、24独立内存。全部CLI显式--events1000。time/内存分开，108后端启动是约定正式资源/科学矩阵预算，不提前运行后段或按结果加轮。tasking/both/Linux资源测量不增为前置。

## 最终语义定稿（直接实施，不再要求作者补一轮报告）

1. **真实载体。** 本MT构建ROOT经SetNtupleMerging(true)合入本run的g4usim.root，并非每worker各一个最终注册ROOT文件；worker部分行保存在合并文件的threadID列。按metadata实际登记文件读取，不按猜测通配符吸收其它文件。hits/events对象在hits负载中检查1000唯一eventID及hits有效行；mesh负载显式hits=false/event_edep=false，其这两个ntuple应为空，不再要求1000条event输出。mesh的全run N从metadata.runs[0].completed_events取1000，与summary核对；ROOT局部n_events按thread的一致值核对、保留记录，不能逐cell/逐行重复相加或要求每worker都是1000。CSV合并所有worker；root只读本run合并ROOT。

2. **稀疏资格和模式。** CollectCells遍历已有score-map键，不保证每个非贡献cell一定没有存储项，故称“实际存储稀疏键”，不把“只非零”当作新判据，不填充41472行。实际三quantity输出名为edep/dose/flux；声明、单位、合法索引、唯一业务键和有效非空贡献核验，记录实际行数。字节占比90%/50%只作负载描述与诊断，不作未经测量证明的硬资格门；输出总bytes/files及后续0.5%守卫仍保留。所有已有字段/列/对象必须检查名称和类型，不得用“只取当前存在列”静默接受删列；CSV v3没有LETcalc/LETstep，不新增占位。runID保留并要求本病例为0。

3. **科学数值。** 删除作者8.2的打印文本半单位、零值0.5容差与3E包络作为通过宽限。12位有效数字不是12位小数；打印0不允许变0.4。hits按完整业务元组（含runID、eventID、trackID、parentID、所有实际科学列）在剔除thread/顺序后比较多重集和重复次数；逐事件edep同样比较，浮点规范化为12位有效数字，有限性先验检查。整数/标签/模式/键集合精确一致。worker合并的summary、scorer/mesh浮点矩用相对误差1e-9、绝对误差0比较，即abs(a-b)<=1e-9*max(abs(a),abs(b))；两零通过，一零一非零失败；不得跳过近零dose/sum_sq。histogram边界保持、所有worker的同bin计数合并比较。baseline各轮及F3-3每一配对都检查，不能只比较中位数掩盖单轮错值。原始浮点/SHA均保留。

4. **ROOT统计与证据变化。** mesh worker部分sum/sum_sq/entries按业务键相加，global N只取一次；不得累加ID。edep_volume/edep_particle及启用量的同键科学矩同样合并，局部worker分配仅作诊断。ROOT已经合并的histogram只读一次，不能再乘worker数。路径、时钟、UUID、逐产物SHA、worker调度划分及预先绑定的候选源码/构建身份是证据变化，不作科学值相等门；但必须独立保存核对。几何/物理/源/单位/量定义/全run事件N/模式/线程设置必须一致。出现未分类的新字段先解释实际消费者语义，不自动忽略。纯csv/root不调用both专用compare_root_csv，不加both运行。

5. **计时/内存。** 原脚本wall_seconds映射total_elapsed_s，不混Python哈希时间；runTimer.Stop之前已发生的worker收尾和master CSV mesh导出在内部wall内，Stop之后的master统计CSV/ROOT最终关闭/metadata/进程退出不在内。RSS限定本次真实Geant4子进程PID+启动身份+路径/SHA，每调用清零，不用进程名、祖先累计峰值或其它任务。100ms采样记录真实间隔/样本与最后成功读数，峰值取各次WorkingSet及OS PeakWorkingSet查询的最大值，最终查询失败不能伪作零或成功，漏峰局限如实保留。允许复用现有测量入口只补最小PID/内存观察接线；最终diff/SHA与分析脚本先经主审看过再跑正式矩阵，不建新框架。

6. **单一瓶颈与门限。** 完成基线后按4个中位全过程耗时选唯一目标，5%内并列时固定优先序hits/csv、hits/root、mesh/csv、mesh/root；先保存target再优化，不看候选收益换目标。还需有真实测量的瓶颈定位依据，源码猜测或单凭最大总耗时不等于定位完成。若需额外诊断执行，只可为冻结目标负载单独记录一次限定profile/分段观察（同输入/程序，事先列观察器与停止条件，经主审核对），不混入正式噪声/收益样本，不加轮追通过；优先复用已有实际时间/CPU/输出证据，不扩工具。目标仍须>=5%全过程改善且5对至少4对更快；其它3点时间回归<=5%；全部4点RSS<=1.10倍、文件数相同/字节变化<=0.5%、科学等价全部通过。MAD=median(abs(x-median(x)))/median(x)<=5%；run wall只辅助解释。竞争任务只记录并等待，不关闭用户程序；硬软件/数据版本固定，磁盘余量/瞬时负载记录但不要求逐字相同。

## 放行边界

F3-1冻结后实际推进F3-2，先由DeepSeek在同一清单项内准备最小观察/只读分析接线及输入身份，主审独审消费者、PID归属和负控后才执行warmup/正式矩阵。该接线不得改产品统计/RNG/输出或实现优化。输入渲染须与原脚本逐字节一致，旧失败/原稿与所有样本保留。阶段及整体软件尚未完成；不因合同冻结宣布性能或科学验收通过。

## 冻结材料SHA-256

- docs/collab/outbox/20261107-f3-contract.md：`5e2cdd4796a883798f71c42c883ab52e22ab9bb0fe76cad1041291254c6d2cb7`
- out/collab/20261107-f3-preregister/parameters.json：`f5abb5a1d69456e06351f90764014dd608d4a2e53a2136ef6c343950f99039de`
- out/collab/20261107-f3-preregister/identity.json：`9ecbf687a3c11125d5a5d9ccf62c5eb9d4dc3d545a417e13ba91b4f33c5357a7`
- out/collab/20261107-f3-preregister/README.md：`0fda45ad450a1c31571888cfa96e502b126d986e282ef805e57d4e9866a83ac3`
