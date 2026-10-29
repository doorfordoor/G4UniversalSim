# R-03 / R-04 当前构建复现（未修复）

2026-10-29，在隔离 worktree 新构建（包含 R-01/R-02 候选修复）上复跑：MSVC Release / Geant4 11.3.2，后端 SHA-256 `4658f847bb29cd91d42eda9f52931207f7762ea0374947fa27ac364007ab2acd`。运行前后哈希相同。

4 个病例各 1 worker、1 事件，另有只构建几何的 mesh 诊断；四个模拟进程均退出 0、摘要 completed。这是反例复现，不是四项通过验收。

- R-03：水母体中有非敏感铅子体；本体质量应为 0.000488 kg，实际 0.0062992 kg。0.1 MeV 本体沉积的 Dose 应为 3.28314884016e-11 Gy，实际 2.5434604934e-12 Gy；无子体叶体对照为正确的 0.001 kg。
- R-04：GDML 辅助属性声明的 `Sensor`、`sensor` 实际仅前者绑定 SD；源在后者时 event_edep=0、无 hits。仅改名为 SensorA/SensorB 后二者均绑定，恢复 0.1 MeV 沉积。

独立计算与 mesh 摘录：[conclusions.json](conclusions.json)。原始输入、命令、日志、CSV、JSON、manifest 等 69 文件共 321180 字节封装在 [raw-evidence.zip](raw-evidence.zip)，逐文件已与 out 中原件比较字节相等；摘要见 [archive.json](archive.json)。使用 ZIP 保留日志/文本摘要原始字节，不让 Git 换行转换改变历史证据。ZIP SHA-256 为 `ea7998a99f1a88278fb23501d253a956d47a153ad3238016fb8046e2c2444174`。

目录外层 conclusions.json 是供阅读的 LF 换行副本，原始 CRLF 字节仍保存在 ZIP 与 out 原件；两种 SHA-256 记录在 archive.json，数值与字段没有更改。归档 ZIP 未受换行整理影响。

原始工作目录为 `out/verification/r03-r04-current/`；包中的绝对路径记录当时真实命令，移动复跑须重新指定输入/输出根。没有删除原件。证据未纳入统一平台 PASS 计数；没有验收全部 MT、replica/parameterised、GDML 显式 sensitive_volumes、bias/region 映射或独立物理基准。
