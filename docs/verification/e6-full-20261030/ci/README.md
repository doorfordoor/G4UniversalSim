# E6 release真实CI证据：通过

冻结提交a779634483d1f077357433c532ccb0d9e3dc5517，分支roadmap/E6-config-compat。freeze时及收集结束本机工作区均clean；只写out，未触发/重跑/取消任何workflow，未改产品或正式测试。此前cb837首轮e6-ci及5bf第二轮e6-ci-final失败原件完整保留。

两个真实push workflow（均run_attempt=1、completed/success）：

- [Linux build and backend regression — 40931653660](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40931653660)：job123651349959 Geant4 11.3.2、job123651349706 Geant4 11.4.3，均success。
- [M0 static and GUI regression — 40931654093](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40931654093)：job123651350890 Ubuntu、job123651350495 Windows，均success。

## 报告与门禁

| 产物 | profile/用例分布 | 报告数 | strict | v3断言执行数合计 |
|---|---|---:|---:|---:|
| linux-evidence-11.3.2 | static21/gui37/backend56/integration20 | 4 | 4/4 | 42779 |
| linux-evidence-11.4.3 | static21/gui37/backend56/integration20 | 4 | 4/4 | 42191 |
| m0-report-ubuntu-latest | static21/gui37 | 2 | 2/2 | 3459 |
| m0-report-windows-latest | static21/gui37 | 2 | 2/2 | 3455 |

总12份报告，384条矩阵用例记录（全pass、0fail、0skip），91884条v3断言执行记录。完整清单为134个用例，不把矩阵重复执行计为384种独立用例，也不把断言入口计数解释为独立物理命题。

所有报告git_head、source_fingerprint、tests_content_fingerprint、用例集合均匹配[frozen-case-manifest.json](frozen-case-manifest.json)，tracked_source_gate均pass。Linux8份报告git_dirty=true、M0四份false，原事实保留；判定使用tracked-source gate与精确内容指纹，不伪造clean报告。

Linux dirty的具体证据和边界：workflow将MAMBA_ROOT_PREFIX设为checkout下`.micromamba`，G4_PREFIX为`.g4env-${version}`，并解包`bin/micromamba`。两份官方job日志均记录解包命令、环境路径、Python/Geant4安装及Transaction finished（11.3日志128/477/513/515行，11.4日志128/472/485/491行），这些生成工具/依赖路径不在Git index、未被仓库.gitignore覆盖，足以使runner的`bool(git status --porcelain)`为true。`build_linux`和`out`已被忽略，不能笼统称构建/报告目录本身导致dirty。8份Linux报告均记录`untracked_source_files=[]`；双指纹匹配只能确认其覆盖的源码/测试内容身份（测试指纹归一CRLF），tracked-source gate只确认指定源目录没有未登记源文件，不代表整个tracked tree未改。**原任务未归档完整porcelain输出/退出码或tracked diff，日志也没有状态清单；确切完整dirty路径及是否还存在指纹范围外/仅行尾差异为unknown，不能宣称Linux测试时是clean checkout，也不能断言只有环境生成物。** [git-dirty-audit.json](git-dirty-audit.json)保存逐报告字段、具体日志行号/摘要及仓库ignore规则核验；此为事后只读审查，没有重跑或改原报告。

- sourcefp：ab79c6c2227518bd7f38d5109998ed0998d8fd53ad500cfbe714d544eb19a474
- testsfp：e9b4f852e36dca85971d40da2c63ed6fd184055358ca965116babba6b16fafd4

[ci-evidence.json](ci-evidence.json)记录完整分布、逐报告门禁及workflow身份，status=passed、complete=true、collection_problems=[]。原门禁输出在[gates](gates)。[raw-log-hash-audit.json](raw-log-hash-audit.json)独立逐项核对384个用例日志原字节SHA，mismatches=0；未用legacy/incomplete选项。[workflow-job-log-hashes.json](workflow-job-log-hashes.json)登记连接器完整解码job日志落盘字节SHA（4份），不是GitHub官方job日志digest。

## GitHub官方ZIP摘要

| Artifact ID | 文件 | SHA-256（与官方digest逐字一致） |
|---:|---|---|
| 12922664065 | linux-evidence-11.3.2.zip | 11281b666c868db6e64e5e0af720d1cb2e5d2223aaf46452ed575b63e7f86abc |
| 12924082053 | linux-evidence-11.4.3.zip | b9235a12d94b4ca9da1867b8860f6d08b0a87bd559706e77a14348eff5be7c59 |
| 12921734390 | m0-report-ubuntu-latest.zip | dfb89e22d1f2175667b31e0f204352f04984573bf3f50e7f2baefb393ade76cd |
| 12924085065 | m0-report-windows-latest.zip | 740a786475e5adad3be307f13cc278edf17d70576acbf9e3a8e666efc37c193f |

官方run/jobs/artifacts元数据按run ID单独保存。ZIP原件与解包原报告/用例日志均保存；解包前拒绝路径逃逸和symlink。元数据、完整job日志、下载均使用已连接GitHub工具；临时下载URL仅内存与stdin管道使用，未打印或保存至脚本/报告，无git凭据读取。两次只读状态查询传输错误另留incident记录，均一次只读重试恢复，无workflow重复动作。

本次证明该提交在真实CI矩阵通过工程测试及证据门禁。配置、GUI与后端运行证据不外推为全部物理结果已经验证；本机Windows全量终态另由root独立接收。
