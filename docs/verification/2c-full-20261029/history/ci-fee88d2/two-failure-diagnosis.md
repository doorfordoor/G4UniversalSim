# 两项 CI 失败只读诊断

范围：冻结 fee88d2840b8300aa315d0feaf21316768f90206 的 Linux 原始 artifact、当前相同相关调用链；未修改 tracked 文件，未启动后端或构建，不干扰 Windows 全量 session51463。

## displacement_damage:203：旧错误文本预期变化，无证据表明缺文件被接受

两版本日志：

- linux-evidence-11.3.2/linux-backend/20261029-134350-438e6db9/displacement_damage.log
- linux-evidence-11.4.3/linux-backend/20261029-134341-cbefea7b/displacement_damage.log

测试 `scripts/test_displacement_damage.py:189` 的缺文件项期望 cannot open NIEL table，`:203` 只因该字符串缺失失败；Runner.run 在此前已经 assert 真实模拟进程非零退出（同文件 :101-103），因此不是缺文件静默运行。实际日志：

```text
G4UniversalSim fatal error: [scoring.displacement]/proton (/tmp/g4usim_ddd_s5l_6cso/case05.ini line 28): Input file does not exist or is not regular: '/tmp/g4usim_ddd_s5l_6cso/missing.csv'
```

`src/Scoring/NielTable.cc:15` 用 InputProvenance::ReadFile；`src/Config/InputProvenance.cc:43` 在文件不存在或非普通文件时拒绝；`src/Scoring/ScoringManager.cc:719-728` 先把相对路径按主 INI 目录解析，再包入 section/key、配置路径及行号。实际错误仍提供主 INI、line 28、[scoring.displacement]/proton、解析后的 missing.csv 绝对路径和明确文件缺失/类型原因，诊断足以定位需要补文件或修路径的输入。此路径未丢失可操作信息。

最小修复建议：只更新这个缺文件病例对错误原因的预期，另断言配置路径/行号、section/key 与 missing.csv 已解析路径，保留 expect_ok=False 的非零退出要求；不放宽为只要失败就算通过。不需要产品改动。若 root 选择保留旧英文前缀兼容，也可在 NielTable 读取捕获处包裹为 cannot open NIEL table + 原因/路径，但这是错误文本兼容选择，不是当前证据证明的功能缺陷。

## interactive_commands:171：成功命令已有可信来源，旧 unknown 预期过时

两版本日志：

- linux-evidence-11.3.2/linux-backend/20261029-134350-438e6db9/interactive_commands.log
- linux-evidence-11.4.3/linux-backend/20261029-134341-cbefea7b/interactive_commands.log

触发 csh 输入为 `/AIHL/app/setNumThreads 2` → `/run/initialize` → `/run/beamOn 2`。两版本均 status=completed、actual_threads=2；旧摘要实际为 effective_threads_origin_kind=macro、origin_file=not_applicable、origin_line=0、origin_key=/aihl/app/setnumthreads。

来源是成功命令，非仅尝试或回填：`main.cc:140-144` 在 ApplyCommand 成功且 handler 失败检查通过后才执行 afterCommand；`main.cc:1021-1023` 的 csh callback 调用 RecordSuccessfulMacroCommand(command, empty file, 0)。`src/Core/SimulationManager.cc:272-292` setter 仅 PreInit、受 CLI 锁约束，先修改真实上下文/MT thread count；最初 runtime_unattributed 在成功 callback 后由同文件 :432-471 确认覆盖。旧摘要为兼容允许枚举继续记 macro，但无来源文件或伪造行号；新的完整 EffectiveConfig receipt 在 :437 根据空 file 明确 kind=interactive，与旧摘要标签分离。

最小修复建议：把 `scripts/test_interactive_commands.py:171` 改为期待旧摘要 macro，并加强断言 origin_key 为实际成功命令、file=not_applicable、line=0、actual_threads=2 和已存在的 completed/exit0。可验证本次 snapshot `/run/threads` 的 interactive 来源和 requested 命令；不能为了恢复旧 unknown 断言删除真实成功命令来源登记。初始化后拒绝病例仍应保持原 main_ini 来源且停止 sentinel。无须产品修改。

结论：本次证据支持这两项均为旧测试预期变化；并非缺 NIEL 输入被接受或失败命令被误标成功。其他 live_progress/sd_context_failure 故障注入问题不在本诊断范围，未混同为测试文本变化。等待 root 授权后再实施。
