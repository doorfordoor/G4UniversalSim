# DDD首候选独立反例

原比较器261项pass，但其完整逐步折积区间证明不成立。counterexample.json保存100MeV可见路径缺口及明确标识为合成的能量账本反例。author-v1.zip/independent-v1.zip保存作者候选与C盘独立新运行、旧比较器、失败的严格路径检查及首次CLI参数拒绝；archives-manifest.json逐文件记录原始SHA/大小，ZIP的CRC与逐文件SHA全部核对。

两个后端各20000事件、exit0；两点参考比较通过，不将验收器错误写成物理模拟失败。`reference.py --check`不受支持，默认调用校验通过；未因此重复后端运行。

可见路径缺口和步平均能量不可恢复的边界应记限制，不能用任意5%门槛或错误能量区间宣布完成。[独审与最小修复提案](../../../collab/reviews/20261105-q2-ddd-reference-review-r1.md)。原始失败保持原身份，不改为通过。
