# Run-summary MT scheduling regression repair

原失败保留：out/collab/run-summary-mt-review/original-run-summary-failure.log及identity JSON。旧temp已删，不能复原其具体worker派发。原宏源码通过仓库脚本保存；新实际对照见baseline/（四次真实执行，全日志、config、macro、所有输出）。

实际反例：baseline/native-2进程exit0，三run各8事件完整；run0 worker0拥有0..7全部primary，worker1无hits_t1.csv；run1/2双方参与。严格新observer验证全部24事件的particle/energy/XYZ及event_edep分配无错，只标双worker覆盖不足。此直接反驳固定8事件必有两份worker hits的假设；不把原失败档案追改成pass，也不据已删原temp断言其物理语义已经核对。

已改scripts/test_run_summary.py：两个小事件MT用例共用严格observer与有界独立attempt，事件数仍8、threads仍2。每attempt核对summary完成/输出/宏状态、总与逐run planned/completed/id、所有实际hits/event_edep文件schema和登记、事件不重复且0..7完整；primary必须与event_edep worker归属一致，逐event检查实际particle/energy/x/y/z。不同worker重复事件不再setdefault静默覆盖。只有同一次attempt的每个run都真实见到worker0/1产生primary才成功。最多6次；语义错误立即失败且不重试；6次仍覆盖不足明确失败。

每attempt在独立持久目录保存全部真实输出、backend log、macro、实际worker-event与primary记录、失败错误；配置inputs拷贝留存。默认out/test-evidence/run-summary-mt/UUID，也遵守G4USIM_TEST_EVIDENCE_DIR；不在TemporaryDirectory退出时销毁这部分证据。最终源码另加二进制/config SHA清单及显式最终覆盖assert。

新增scripts/test_run_summary_mt_observation.py：稀疏合法但不算覆盖、双worker合法、错误能量/位置、缺事件、跨worker重复、真实有事件但缺hits、最多尝试耗尽必须fail、语义错误只执行一次。当前原venv probe exit0/11个目标文件assert入口；导入observer内断言不计入这个独立target，不虚报计数。负例日志observation-negative-tests.log。

真实Windows11.4完整run_summary probe exit0/28715断言（windows114-candidate.log），两种MT用例均首attempt真实双worker各run满足。该进程启动后仅追加过显式最终覆盖assert和identity.json记录，不改运行/语义判断；为避免冒充最后文件已整套执行，另独立执行最后源码的实际MT窄helper并在current-helper/identity.json绑定脚本/EXE SHA。当前session19255待收尾，current-helper.log。

只改test_run_summary.py及新增窄测试，无产品/宏/报告门槛变化。未提交。root需把新增窄测试登记进static profile并以最终源码跑正式矩阵；当前证据不替代其余平台/版本正式验收。
最后源码窄helper已完成session19255 exit0：source/native各首attempt真实双worker覆盖全部run、8事件完整且所有语义断言通过；current-helper/identity.json保存实际脚本与EXE SHA并检查执行期间源码未变。没有剩余运行session。py_compile和git diff --check通过。
