# E6 5bf479d CI 原始失败证据

冻结SHA 5bf479d85ba7c12e0f71984d31b8335c47c5a8c3；133项名单static21/GUI36/backend56/integration20。sourcefp ab79c6c2227518bd7f38d5109998ed0998d8fd53ad500cfbe714d544eb19a474；testsfp 030a614bd92124c1b396140824b1cac549bd8d0d3d48e0508e67a19383a4db7c。

实际push、attempt1、未取消或重跑：
- Linux run40926120374：Geant4 11.4.3 job123631968565、11.3.2 job123631968946，均failure。
- M0 run40926120368：Ubuntu job123631968440 failure；Windows job123631969002 success。

四job static21/21均通过。M0 Windows GUI36/36通过；三Linux job GUI35pass/1fail/0skip，唯一gui_project_import_projection。失败记录exit_code=-6、assertions_executed=393；日志已打印断言marker，随后在Python runtime finalizing阶段Fatal Python error: none_dealloc: deallocating None: bug likely caused by a refcount error in a C extension。缺CJK glyph只是前序UserWarning，不是根因。这里不能由断言执行完成推断进程成功。

两版Linux的backend/integration步骤因GUI失败未执行，没有这四份profile报告。实际8份报告而非预期12；strict门禁5份通过、3份GUI报告因失败case拒绝。仅诊断--allow-incomplete三份均通过，说明允许非通过case时报告内部断言/日志证据约束自洽，不等于release通过。

四份官方ZIP均已下载并与GitHub artifact digest匹配；run/jobs/artifact官方metadata与四份job日志均保存；全部228份报告日志raw SHA256与声明相同，raw-log-hash-audit.json列出结果。ci-evidence.json为not_passed、complete=false，正确保留缺失profile分布。

一次M0 job-status连接读取发生传输失败，原文connector-status-read-incident.log；一次只读重取成功，未触发工作流重跑。随后所有metadata/日志/归档都经已有GitHub连接获得，不需要读取Git凭据。

本目录只对应5bf479d这次真实失败；首轮cb837e6证据仍在e6-ci，均不改。后续修复/重新冻结须另存新身份，不用绿色结果覆盖本次失败。
