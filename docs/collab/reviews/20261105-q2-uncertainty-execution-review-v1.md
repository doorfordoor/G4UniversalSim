# Q2-4 执行候选 v1 独立审查：需要修复比较证据

2026-11-05，原任务 round85 / turn70 已完成、停写。冻结合同 SHA `5768cc413d7e05b586fdbe8074342e52ec14cdbf27fbc037163604775e0381b6`；原比较结果 SHA `3529cb987b687d29d47e42636d38be061dd3fff6c0f6c4cac8d9caa6b9042cc8`。此处判定针对验收证据；没有据此认定物理后端输出错误。

1. `tamper.py:157` 的 CE-WORKER-AVERAGE 只复制一条 event_edep 行到两个 worker，既未把主统计值换成 worker 误差平均，也未建立可区分的预注册 fixture。触发重复事件行不是这条反例的检出证据。原稀疏运行只有 worker 3 非空，按冻结约定不得换种子。可用一次性 fixture：两个 worker 的每事件贡献分别 [1,1]、[0,4]，真实组件 Submit/Take 合并 N=4、S=6、S2=18、entries=3，R=0.5；错误平均 R=(0+sqrt(0.5))/2≈0.353553390593。以正确行通过、仅替换 R 后由 MT-NO-WORKER-AVERAGE 或 MT-DOSE-STATS 拒绝为准；worker 各自两事件属于合成组件，不冒充 N=2 的真实 Geant4 分配。
2. `compare.py:682` 的 MT-LET-MERGE 计算 B/A、C/B，却只比较两种 R，没有对账公开的比值；改一个 master LET value、保留其余数据不会由该检查发现。核对两个公开 master value 与合并矩的比值及单位（MeV/mm 和 keV/µm 数值相同），同时保留 R 检查。
3. `compare.py:827` 的 COV-PATH 检查路径及注量矩，未核统计 entries 等于 K；只改 entries 不影响该检查。按冻结合同核 raw/weighted 路径与注量统计的 N、entries、S、S2 与估计方法，在实际字段上完成对账。原覆盖 K 范围 1351–1436 **并非** [1347,1429] 的子集，唯一正常未覆盖批次保留；汇总报告应写 63/64、总 K=88809，不能把单批未覆盖改成失败。

仅修比较、组件/副本反例和报告。保持全部 69 次原始运行、输入、身份和冻结合同字节不变；不要重跑、增样或改门槛。保留初版失败与交付，修正后给出原件哈希、真实组件收据、阳性/阴性对照及具体复演命令。
