# DDD修订报告：受限签收

整体结论是**limited**，不是完整折积验证通过。修订比较器263项为257 pass / 0 fail / 6 limited；两个物理参考项仍满足原1%加3σ。独立可用数据复算51项，另列观测限制；7个副本反例真正产生fail，原始数据和运行记录未变。

author-r1.zip与independent-r1.zip保留修订源码、原始输入/输出、反例和修订材料。独立包中的independent-r1-recheck.json是本次复核收据，independent-math-r2-results.json是可核实部分的受限数学结果；旧independent_math.py及旧失败日志是保留历史，不能冒充新通过材料。pre-observability-r1-results.json保留旧261项判定。

archives-manifest.json列每个ZIP及内嵌文件的原始SHA/大小，全部CRC及逐文件SHA已核对。原两个后端在此前C盘新目录各完成20000事件、exit0；修订只重新分析和验证反例，没有再运行Geant4。固定产品864bc036、Windows/11.3.2、EM-only、两个种子范围不扩张。

普通hits可省略零沉积步且缺步平均动能，因此完整路径/事件全集/逐步折积保留限制；不以放宽容差掩盖。[独立签收及限制](../../collab/reviews/20261105-q2-ddd-reference-review-r2.md)。旧错误证明和首次反例仍独立保存在q2-ddd-review-20261105/first-counterexample；Q2未关闭。
