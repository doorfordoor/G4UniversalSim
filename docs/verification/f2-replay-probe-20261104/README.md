# F2 协议待决期间的单worker比较准备

主审2026-11-04，未修改产品。参照原件为../f2-baseline-20261104/independent/three-round/，本包保存第二次相同stdin/config seed1904、1worker的A/B/A及比较结果。后端SHA、环境及配置相同；没有为比较再次重建程序。

1. 实际第二个后端正常退出0。初始驱动对全部24个CSV原字节作严格断言，**驱动退出1**：21个相同、3个scorer_statistics表不同。原始失败report与driver.log保留，没有追改或重跑掩盖。
2. 无需重跑，直接检查同一组原件：3个表的差异列仅fom_per_s和run_wall_time_s。按照既定F2排除时间等非确定元数据的规则，仅排除这两个时间/性能列后，24个CSV的其余单元格字符串严格相同；未加数值容差、未删除物理统计列、未排序隐藏物理差异。replay-physical-analysis.json逐文件列出差异及排除项。
3. 这是固定启动seed及命令序列的比较准备，尚未独立捕获完整随机引擎初态文件，也不是新协议、MT或完整F2重放验收。多worker及正式回放仍按原清单实施验证，不能以本包提前通过。

replay_probe.py为执行时的一次性脚本原件，运行根为C盘独立OUT；不要在冻结归档内直接重跑。复现时在独立OUT复制原配置及参照three-round目录，再复制脚本；保留原件。本包manifest.json只登记复制原件，不自包含或包含本说明。
