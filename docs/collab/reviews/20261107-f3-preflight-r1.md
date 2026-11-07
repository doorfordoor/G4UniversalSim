# F3-2 首次接线独立复验

2026-11-07。原round150/turn118已completed；最终observer423cabd6、comparator b5afba15、测量脚本5b71d537。结论：首版未通过，正式矩阵不放行。仅修F3-2当前观察所必需的缺陷，不扩清单、平台或框架。原交付快照及37/37自检原件保留out/collab/f3-preflight-independent/r1/final与author-selfcheck-original。网页observer/science二审均已completed；以下经主审核实/复现归并，不以优先级标签冒称后端产品缺陷。

## 已复现反例与最小修复

1. **PID/峰值终态。** reproduce-blockers.log及probes/b53ac282-acc1-4817-acbe-fe8713e993ee/results.json：普通自有Python child仍alive，observer在0.15s超时、16样本、final_query_ok=true却exit0；控制first/loop/final三次成功读数100/20/200，公布peak只有20。修pid_observer：用进程句柄真实退出状态区分正常退出、存活查询失败和timeout；后两者必须非零，首末所有成功读数都纳入max(WorkingSet,OSPeak)。最终查询不可用如实保留false/last_success及漏峰局限，不能把进程存活失败当退出。launcher记录并传入实际Popen创建FILETIME、冻结exeSHA，观察器核PID/创建时间/映像路径/SHA。measure脚本验证观察终态/有效样本/绑定信息，任何异常只回收该调用自有的两个Popen，不残留后台观察器。

2. **真实ROOT数值类型与MT全局N。** science-core-probes.json：已存在的真实Geant4 ROOT（E4 Linux安装runtime原件，SHAdebbdb9c…）对自身compare_moment_tree即报float不能用于range；其n_events分支真实是double，不是自检fixture里的整数。tree_rows按实际数组长度/经严格完整性校验的整值num_entries读取；canon_value必须接受有限且数学上为整数的ROOT double计数（1000.0），拒绝小数/NaN/Inf，禁止int截断。自检ROOT fixture按AnalysisOutput真实I/D类型建表。稀有gamma科学矩相同、全局N两侧1000，仅贡献worker局部N300/500时，当前按稀疏键相加的events不同而误拒；用同run metadata全局N，局部N只按worker核一致/范围，不把贡献worker N之和作跨候选科学相等门。

3. **科学文件/字段漏检与非有限值。** 独立合成反例：登记CSV histogram count 1→999仍pass；ROOT内容不变、scorer_statistics.sum改100仍pass。classify/compare_csv应覆盖实际登记的hist_edep与逐体积/粒子summary，合并全部worker比较已有科学列；ROOT格式同样比较master statistics CSV。已登记未知科学文件显式分类/拒绝，不能静默unknown略过。similarity_check(1,+inf)当前零fail，有限性须在任何相等/容差分支前验证，覆盖ROOT矩/hist edges和合并溢出。mesh的rel_error、estimator/status、global n_events当前被读后丢弃，独立修改它们仍零fail；按原schema比较/验证，CSV key唯一、三quantity/单位和0..23索引检查。按冻结合同补各run资格status、planned/completed1000、runID0、hits有效行与events集合/重复；mesh负载允许关闭events而非强求输出。去掉对effective_/planned_/actual_全部前缀放行，区分真实源/物理/量/线程配置与纯路径/时间/身份。只覆盖本次实际消费者，不泛化到未启用LET/DDD。

4. **冻结运行顺序。** run-plan.json当前按hits/csv的warmup→5timing→3memory，再下一个combo，改变已冻结顺序。改成3条全矩阵调用：4combo warmup一轮；4combo正式5轮（repeat外层，hits→mesh、csv→root）；最后rounds0/memory-repeats3独立内存12次。共36后端执行不变，CLI显式1000事件。输出使用新的正式目录，不能默认写入selfcheck/run-plan既有目录。bottleneck排序/时间分解只作目标和诊断，跨格式差值不能自动证明具体函数热点；基线后按冻结决定给实际定位依据，不因此先扩profiler。

## 修复范围与停止条件

仅scripts/measure_output_performance.py及既有preflight的pid_observer.py、science_compare.py、selfcheck.py、run-plan.json与必要hashes/README/measure.diff。不得改后端/GUI/合同/清单/统计/种子，不新增patch_*生成器或通用工具，不整理无关文件。沿用已有自验，仅补上述会漏检/误拒的真实反例，保存旧日志/报告，不用更多报告代替修复。

交回准确新SHA、精简修复回执及ready_for_run_review；主审复验这些最小反例和原模板字节后立即放行正式矩阵。此轮仍禁止Geant4 warmup/正式baseline/profile/优化。独立探针只运行合成数据/既有ROOT读入/自有普通Python child，未运行模拟或性能。
