# K1 Windows CP1252 diagnostic candidate — single smoke file

唯一候选 `files/gui/smoke_tests/smoke_k1_workflow.py`。基线 `4167c4421b13464dec54213ea7652ee321868c4e`；作者Tesla/gpt-6.1-sol high，usage unknown。只改一处JSON参数 `ensure_ascii=False` → `True`；不删除诊断、字段、断言或改业务判据，不修改产品、runner、正式运行源码或tracked。作者测试不作独审签字。

## 原CI事实（先核原log）

M0 Windows run 41179691469、job 124474368833，gui_k1_window exit1 / v3 76。原log先输出英文variant0，然后在smoke_k1_workflow.py:191诊断print经encodings/cp1252.py编码时UnicodeEncodeError；中文显示回合尚未执行该print之后的观察断言。不能说原CI已发现cwd判据失败或已经证明后续UI通过。facts/log/report实际原字节SHA均核对，副本保存在本目录evidence/，原始文件未改。

- 原facts SHA `57f56db493b3b3308cac8ace46d7b047c9ee974cf1f5b99dde4d76ffae44a029`
- 原log SHA `ac9b6aa0d0015cd47461038f7eec54b5bdfd6b19e3c04eb5ebb883678e120346`
- 原report SHA `3de0462014b40965a3ab671d432e81c0c79387dd678c65c7c8488082271d5ea9`

## 窄范围红→绿

同一Python311、实际第六产品、同一CP1252 stdout pipe、Qt offscreen与原tools/test_assert_probe.py：先跑未改原smoke完整镜像，exit1/76，精确同一第191行print和cp1252 UnicodeEncodeError；后改一处参数，候选完整镜像exit0/178。负例和正例的命令、日志原字节SHA、退出码与计数分别在baseline-cp1252-receipt.json、candidate-cp1252-receipt.json。

镜像仅一份测试脚本，真实ROOT仅用于原脚本sys.path入口；依赖从PYTHONPATH加载未改checkout的产品/现有fixture。直接执行原assert probe及runpy；没有截取AST运行、替换import/runpy、伪造后端成功或跳过Qt/服务/清理。真实Generate、真实external _prepare、受控completed显示形状、generated/F5/关闭流程均按原smoke执行；本smoke本就不运行Geant4模拟。TEMP/TMP仅本OUT临时根，正负一致，不修改Windows设置或父进程环境。

正例全部10条诊断为ASCII字节，JSON解码仍恢复中文与深目录emoji，五种形状×中英文完整保留；整smoke正常结束意味着原失败print之后断言及后续原检查执行完。74个assert完整AST逐个完全相同；全文件AST唯一差异也只是ensure_ascii布尔值。补丁apply --check通过。没有另跑panel、全量或正式矩阵。

## 身份与交付

- 候选SHA `e653d5d67d50ba2956a5e6b16d378b74abf085075c8093800b85b2c1d71c6632`
- 补丁SHA `903d079875c6933f0321b2707bfd95a225a4ad3d20a5da04ef76b179ebef2fe8`
- 原probe SHA `fd6515504cdec5ab86046e53e390cb366f49ee5facbf7acbe21314943ad8568c`

`candidate.patch` 为相对第六基线的单行补丁；manifest.json锁定候选与全部证据；checks.json为断言/序列化/字节核对。旧CI原件、旧UI候选与旧审查报告保持原样；本候选等待父任务及独立审查，不能自签或宣布K1完成。无资源边界scope。

如需重放，先复制到另一个允许OUT目录（本轮日志用排他创建，原件不覆写），再运行：

```powershell
python -B out/collab/k1-encoding-candidate/run_case.py baseline
python -B out/collab/k1-encoding-candidate/run_case.py candidate
```

run_case.py只对其子进程设置PYTHONIOENCODING=cp1252；负例预期子进程exit1，正例预期exit0，包装脚本自身成功保存结果不是测试通过的替代。
