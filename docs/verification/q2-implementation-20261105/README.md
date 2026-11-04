# Q2-2 Windows实现层独立复验

冻结后端864bc036/e7de615d、SHA f8a8119d，原始来源见归档identity.json。C盘新目录重新生成输入，独立运行四类、五个真实后端进程（LET两能点），均exit0。修复后的比较器201项通过，27个产物副本反例全部检出。原删除摘要和metadata仍pass的反例现exit1并输出明确失败项。

Windows实现层范围签收通过。原运行、输入、比较器、篡改器及结果逐文件摘要与ZIP CRC核对，保留在windows-independent.zip。跨平台与正式回归归Q2整阶段验收，外部物理参考及覆盖率归后续条目。
