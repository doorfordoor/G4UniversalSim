# LET独立参考 v1：失败证据

2026-11-05。冻结文件、原实现交付和C盘新目录独立运行分别保存在author-v1.zip、independent-v1.zip；archives-manifest.json列逐文件SHA/大小及ZIP身份。已检查全部CRC和归档内逐文件SHA。原文件继续保留，不删除、不覆写。

两例后端各exit0、2000事件；控制脚本exit1，因为比较器101项中REF-LET-D-REL一项失败。10/100MeV的LET_t外部参考比较均通过，100MeV的LET_d与LET_t相对差21.06%，超过原冻结5%。整例v1仍为失败，不是阶段通过。

独立矩重算及过程事实见independent-review.json；individual-ratio-error-independent.json另保存两个病例的四个比值误差区间复算（12位有效数字的半单位区间传播），均与输出吻合，不含两个比值差的协方差验证。判据适用域和后续隔离实验见[独审](../../collab/reviews/20261105-q2-let-reference-review-v1.md)。本页只记录Windows该后端及两固定种子，不外推Linux、云CI、其他物理列表或Q2整阶段。
