# F5 新冻结候选：官方 CI 完整独立审计通过

候选：`5c1eec5007cd29cbe12949c19bed81457f1f825b`，分支 `roadmap/F5-transactions-recovery`。官方 push/attempt 1 的 Linux [run41090605959](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41090605959) 与 M0 [run41090605955](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41090605955) 均 completed/success。未 dispatch、未重跑挑绿、未借用旧 SHA 产物。

`evidence-integrity-audit.json/.log`：完整独立审计退出码0、status=passed、problems=[]。实际核验4个官方ZIP、521个提取文件成员、12份报告、478次用例执行、113061条v3执行断言。`ci-evidence.json` 是摘要入口；`frozen-case-manifest.json` 是root冻结原件。

| 官方产物 | static | GUI | backend | integration | 执行数 | v3合计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Linux 11.3.2 | 32 / 2715 | 47 / 3249 | 59 / 40416 | 22 / 4486 | 160 | 50866 |
| Linux 11.4.3 | 32 / 2715 | 47 / 3249 | 59 / 39824 | 22 / 4486 | 160 | 50274 |
| M0 Windows | 32 / 2706 | 47 / 3251 | — | — | 79 | 5957 |
| M0 Ubuntu | 32 / 2715 | 47 / 3249 | — | — | 79 | 5964 |

每格为用例数 / 已执行assert数；不同平台/Geant4版本各自与F4同平台同版本profile比较。12份严格F4逐例、逐profile门禁全部通过，无fail/skip/零断言用例。每份报告和所有逐用例日志原字节SHA、v3 marker与逐项求和一致；Linux两个官方篡改日志负向对照均明确拒绝。四份实际Qt运行版本与binding-lifetime收据、两版共六次原生helper用例及其构建完成记录均通过独立检查。

## 同一冻结身份与工作区状态

- 12份报告都为同一5c1eec5；source fingerprint `db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc`；tests fingerprint `5328e3515e882c69585cbfceeb43ca0e5f480c925e8336072b6cbdfc22de2109`。
- Linux backend/integration真实构建身份分别为Geant4 1132/1143、GNU、Release、MT；后端/merge构建来源门禁匹配。没有沿用F4历史双提交例外。
- Linux全部8份报告保留原值 `git_dirty=true`，其原样porcelain只列 `?? .g4env-11.3.2/` 或 `?? .g4env-11.4.3/`，以及 `?? .micromamba/`、`?? bin/`。这些路径与冻结workflow的环境前缀/解包位置对应（workflow第37–38、52–61行）。这是已观察到的未跟踪目录，不能把整个Linux工作区称为clean；tracked-source inventory及源/测试指纹是另外两项通过的证据。
- M0全部4份报告 `git_dirty=false`，原样porcelain为空。

## DDD 原始证据与稀疏 N 边界

两个Linux DDD用例均为73次v3断言，不再随统计行数改变。每份backend报告的 `displacement_damage-evidence/first-run` 保留输入、CSV、metadata、summary原字节及manifest；独立审计校验所有manifest文件的安全唯一相对路径、大小和原字节SHA，未仅相信测试自报。

- Linux11.3.2：12文件、58791字节；t0两行（e-/mu-，每行N=200），t1只有表头，N记unknown/null。可见worker去重N=200，master=200。
- Linux11.4.3：13文件、59635字节；t0两行且每行N=190，t1两行且每行N=10；可见worker去重N=200，master=200。
- 每粒子行重复携带该worker N，所以不能按行相加。审计契约是可见worker去重N为完整master N的下界，即 `0 < observed_N <= master_N`；空表头不能单独证明零事件，也不要求每个有行worker都有mu-。两份本轮收据恰好相等，不扩大为一般稀疏输出必然相等。
- 本归档是证据子集，原输入的绝对路径记录原临时环境，不是可搬移后直接运行的工程；captured-process.log是解码文本记录，不能称原始管道字节。

旧5d56187的DDD 44<46严格门禁失败原件保持；本次通过不追改旧报告、不用新口径重算旧断言。新实现的确定性稀疏合法/错误反例与真实专项交接另见out/collab中的r3记录。

## 官方 ZIP 摘要

| Artifact ID / 名称 | 字节数 | 官方及本地一致的 SHA-256 |
| --- | ---: | --- |
| 12995900114 / linux-evidence-11.3.2 | 106503 | `1f2a1412be9afc4f3641fd352fae47485f443deaf9acaf8d463b845c8af48347` |
| 12994897698 / linux-evidence-11.4.3 | 107194 | `36778828e85e28e585d2f3e74de346a0b73af374363173706c69d25c5801a35e` |
| 12993942643 / m0-report-windows-latest | 32465 | `9a093f5f6619ac53d713c66fb25945de3c808ce7ac1b763f6b01e2007d33f156` |
| 12993188333 / m0-report-ubuntu-latest | 35092 | `0e86f5b89888462e2431b5b612c68c02527cb4137ac3c17f4d90a2cdb5f38967` |

官方run/jobs/artifacts API原文、四份完整connector解码job日志、四ZIP及每个提取成员均保留。临时下载URL仅在内存经无回显stdin传入，未写入任何证据。初始API、M0中途审计和早期门禁是原样过程收据，不应当成最终状态。

## 验收及归档边界

本审计只证明该提交的正式CI范围。Windows本机160用例全量、实际窗口验收和F5阶段关闭由root另行计证；不以CI通过推出物理模型已获外部实验验证。

root补充的 `windows-build/capabilities.json`、`capabilities.stderr`、`receipt.json` 已纳入归档。独立复核capabilities与收据原字节SHA、当前本地后端可执行文件SHA、同一5c1eec5/source fingerprint、Release/MSVC/Geant4 1132/MT；这只核对构建身份，不替代本机全量或窗口验收。复核记录为 `windows-build-verification.json`。

最终 `archive-file-manifest.json` 在本说明、摘要与构建收据齐全后最后生成，逐文件列出SHA和字节数。除该清单自身与明确列出的 `__pycache__` 外，不静默遗漏文件；清单生成后目录冻结，归档须按清单核验，不能用后来重新计算的目录摘要替代。
