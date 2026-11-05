# H2-4 首交付独立审查：V7阻断
2026-11-06。H2-4失败，不能把原要求首事件前拒绝降为可签收限制。

独立复现原v7_muon.ini/mac，输出隔离至out/collab/h2-benchmarks/independent-v7：exit1，status=failed，output_failure_stage=scoring_filter_particle，但actual_completed_event_count=run_0_completed_events=10。原始日志/摘要保留。此结果直接违反冻结0事件要求。

定位：RunAction::BeginOfRunAction调用ScoringManager::BeginRun，未知粒子失败后catch记录失败、AbortRun(true)、return（约138-147行）。此路径没有可靠保证事件循环未启动。不要只把摘要完成数改0，不要在worker无保护抛异常导致崩溃/无失败摘要。

最小修复方向：在粒子表已就绪、事件循环启动前完成此配置校验并可靠拒绝本轮；复用既有运行失败/会话拒绝机制。若使用run初始化失败标志，须在任何事件生成之前生效且跨worker一致，不是处理完首事件再中止。保留未知粒子原失败阶段与非零退出，配置失败不得继续后续beamOn。最小文件范围ScoringManager校验与RunAction/必要主运行入口；不要改变计分公式。

验收反例：原V7单线程10事件必须实际0事件/无科学数据，摘要如实failed；另在受影响多线程路径用相同小病例确认无worker继续处理。合法V5仍100事件。脚本test_h2_benchmarks.py不能以limited返回成功掩盖此阻断，修复后对0事件明确assert。只补受影响测试，不重跑Q2。

其余进展：独立从原始CSV按12位有效数字区间复算V1a dose/fluence分区及V4两run的dose/fluence谱和，均通过，结果out/collab/h2-benchmarks/independent-partial-review.json。V6a/DDD详细独审未完成，不能统称全基准通过。

执行阻塞：本轮/tasks/get与随后/health均WinError10061连接被拒。旧h2-state.json仍为上轮running缓存，不能认作当前状态。未重试写入、未重新绑定、未派发修复。恢复桌面桥后先查原任务终态/队列，再按本审查派发唯一请求h2-v7-pre-event-fix-20261106-r1。