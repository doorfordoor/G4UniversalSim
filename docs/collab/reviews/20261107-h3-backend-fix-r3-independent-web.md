# H3-2 后端修复 r3 独立复审（2026-11-07）

**结论：本轮限定的 H3-2 冻结合同审查未发现新的 P0/P1 阻断缺陷。** 既定四个历史反例按原输入字节独立复演符合预期，三个已有 backend 用例在隔离临时目录后全部通过，源码 A–I 链路已按下述边界核对。建议主审按此证据决定 H3-2 是否验收。本结论不代表 H3-3、H3-4 或 H3-5 通过，也不将物理统计等效性视为已验证。

## 一、按优先级排序的发现

**P0/P1：本轮未发现新的、符合既定冻结判据的可复现问题。** 因而没有需提交给实施者的新增最小修复范围。历史失败仍保留其原始证据和失败身份，以下仅记录 r3 候选对既定反例的独立重演。

| 历史问题及触发反例 | r3 对应代码 | 本轮冻结程序实测 | 当前裁定 |
| --- | --- | --- | --- |
| r1 P1：质量世界 `WaterBox` 自身绕 Z 旋转 90°，而平行盒未旋转，原来误报整盒同材料 | `src/ParallelWorld/ParallelWorldConfig.cc:619-646,695-785` | `self_rotated_water_box`，exit 0，dry_run；最终字段 `material_matches_mass_world` 精确为字符串 `unknown` | 原反例修复得到复验支持 |
| r1 P1：水母盒内部存在半径 0.5 mm 的铜球，原来忽略非 box 异材质后代 | 同上，特别是 `:761-772` | `copper_sphere_descendant`，exit 0，dry_run；最终材料证明为字符串 `unknown` | 原反例修复得到复验支持 |
| r2 P1-1：`/AIHL/geometry/loadConfig` 在 PreInit 把 `Slab` 从 water 改为 copper，原来保留旧 `true` | `src/ParallelWorld/ParallelWorldConfig.cc:826-855`，`src/Core/EffectiveSimulation.cc:190-205`，`src/Core/SimulationManager.cc:1343-1384` | `lifecycle_geometry_switch`，exit 0，`status=completed`，run 0 计划/完成 20/20；质量侧 `Slab.material=copper`，平行侧 `Slab.material=water`，证明为字符串 `unknown` | 原反例修复得到复验支持 |
| r2 P1-2：世界坐标约 1,000,000 mm，两个 2×2×2 mm 盒有 0.0005×2×2 mm 的正体积交叠，原来当作贴边 | `src/ParallelWorld/ParallelWorldConfig.cc:43-48,512-539` | `positive_overlap`，exit 1；stderr 明确为 `overlap in their interior`，在 dry-run 配置阶段拒绝 | 原反例修复得到复验支持 |

四例原始输入在 `out/collab/h3-independent-r2/material-negative-repro/`、`out/collab/h3-independent-r3/`，本轮只复制 `.ini`/`.mac` 并逐文件核对源副本 SHA-256，保存到 `out/collab/h3-independent-r4/repro/<case>/`。各例的 `case_result.json`、原始输入、stdout、stderr、真实摘要和有效配置在对应目录；合并记录为 `repro/results.json`。前三例的结果来自 JSON 字段解析，交叠失败来自实际进程退出码及原始诊断。

## 二、A–I 源码审查范围

按 `docs/collab/outbox/20261106-h3-backend-fix-r1.md` 定义的 A–I 核对，未把接口存在直接当作物理正确性证明。

| 项 | 已核对的真实路径和边界 |
| --- | --- |
| A 名称、网格、交叠 | `src/ParallelWorld/ParallelWorldConfig.cc:188-220,271-478,486-539`：名称和展开后单元唯一性、4096 上限、正体积交叠及面接触区分。`CoordinateBound` 在 `:43-48` 替换旧随坐标放大的容差；远坐标正交叠已实测拒绝。 |
| B 材料整盒证明 | `src/ParallelWorld/ParallelWorldConfig.cc:603-671,695-785,826-855`：只对无旋转/正常放置的可投影 box 签发整盒对应证明，异材质且不可投影的后代保守降级；几何切换后重绑并刷新。四项历史反例及未旋转叶盒、材料别名、平移层级正例由既有 `parallel_world` 测试覆盖。 |
| C 参考质量和数值门禁 | `src/ParallelWorld/ParallelWorldConfig.cc:364-469,502-509,542-581,713-734`：尺寸/中心/体积、密度/参考质量/总质量正有限检查；`src/Core/SimulationManager.cc:1406-1458` 比对 ghost 盒实际半长、质量并检查包含。 |
| D 有效配置与逐 run 收据 | `src/ParallelWorld/ParallelWorldConfig.cc:864-981`，`src/Core/SimulationManager.cc:629-668,819-865`：Run 完成条件、该 run 的实际事件数、已关闭输出的 SHA、finalization/metadata 文件登记顺序。后述 20 事件运行独立验算。 |
| E 运行期禁用组合 | `src/ParallelWorld/ParallelWorldConfig.cc:790-824`，`src/Core/SimulationManager.cc:1350-1384`，`main.cc:973-991,1063-1073`，`src/Core/SessionServer.cc:1558-1571,1660-1670`：ROOT、biasing、原生 mesh、field、LET、DDD 的 live 依赖复核，并覆盖 batch、csh 和受控 session 的初始化/运行前入口。自动测试的受支持负例通过。 |
| F copyNo 与路径 | `src/ParallelWorld/ScoringParallelWorld.cc:53-80` 的每个物理体 copyNo=0；`src/ParallelWorld/ParallelScoringDetector.cc:74-81,106-118` 验证叶 copyNo 并按 touchable 全路径加 `#copy`。实测 CSV 为 `/ScoringWorld#0/Slab#0`；网格由既有测试复核。 |
| G 注册与物理列表 | `src/Detector/DetectorConstruction.cc:30-43,61-69` 在 Geant4 用户初始化之前注册；`src/Core/SimulationManager.cc:1214-1231,1233-1281` 在 reference/自定义物理列表均注册 `G4ParallelWorldPhysics(name,false)`。 |
| H ghost 步与独立计分 | `src/ParallelWorld/ParallelScoringDetector.cc:52-124` 从 ghost step 填入完整路径、声明体积与参考质量；`src/Scoring/ScoringManager.cc:737-775` 的 `ScoreParallelHit` 只路由 dose/fluence，避开质量侧 hits/event_edep 广播。`src/Actions/ActionInitialization.cc:90-99` 设置线程本地 ScoringManager。R-COMP/R-RUNTIME/R-SAME 已由既有用例执行。 |
| I 线程 SD 绑定和失败锁存 | `src/ParallelWorld/ScoringParallelWorld.cc:85-120` 在各线程 `ConstructSD()` 查找/建立本线程 SD 并复核绑定；`src/ParallelWorld/ParallelScoringDetector.cc:52-61` 在真正命中时检查 TLS，无 manager 时锁存共享输出失败并请求终止。组件测试包含缺失 TLS 的失败登记。 |

## 三、独立运行、收据及身份核验

- 冻结 `out/collab/h3-independent-r4/bin/G4UniversalSim.exe` SHA-256 为 `14b9f29e7b71bac9beb1c582582c7deeab3e27d73faae958ee46d083fcd09537`；`parallelScoringCheck.exe` 为 `2525be0a3e8ed4d1c0ed15f0ce412b069bf64aecfc548798b712e0645c6c1eb2`。`capabilities.json`/`identities.json` 中源码指纹为 `860b54b2982f1d50d2d414b74eb21864243250874d7a4770a1b4a94245dff114`。按 `source-sha256.json` 逐一重算 24 个 source 快照和当前同名源码/测试文件的 SHA，均 0 差异；本轮未重算编译器源码指纹，也未使用正在变化的构建目录程序。
- 首次运行现有三个 backend 用例的报告为 `out/collab/h3-independent-r4/verification/20261107-015342-39283d50/report.json`，均因系统默认 `D:\Temp` 的 `Access is denied` 停在测试临时目录创建/清理，属于该次测试的环境失败，**保留原始 0/3 记录**。不修改代码、输入、测试脚本或 EXE，只将该命令进程的 `TEMP` 和 `TMP` 设为 `out/collab/h3-independent-r4/tmp` 后独立复跑。
- 有效复跑报告为 `out/collab/h3-independent-r4/verification/20261107-015428-226c9a5c/report.json`：`run_summary` PASS（37271 次已执行断言），`parallel_world` PASS（2411），`parallel_scoring_component` PASS（8），**3 pass / 0 fail / 0 skip，合计 39690 次已执行断言**。调用的是既有 backend profile、三个既有 case 和上述冻结 EXE，没有构建或引入新验收框架。
- 对真实 20 事件运行逐项独立读取 `effective_config_finalization.json`、`run_summary.txt`、`run_metadata.json`、CSV，并复算磁盘 SHA：有 1 条 `run_validated`（`run_id=0`、`completed_events=20`、`volume_count=1`），其 12 个输出哈希全部匹配；metadata 列出的 16 个文件与摘要列出的 16 个路径逐一相等且均存在。metadata 里 15 个携带 SHA 的文件实算全部吻合，metadata 自身为未携带自引用哈希的第 16 项。质量侧 copper/平行 water、声明参考质量 0.0008 kg、dose/fluence 行的 `runID=0`、`n_events=20`、`/ScoringWorld#0/Slab#0` 都已实际读回。审计机器可读记录为 `out/collab/h3-independent-r4/source-output-audit.json`。

## 四、已审与未审边界、验收建议

**已审**：冻结合同与监督状态、r1/r2 失败和 r3 修复回执；四例独立真实进程复演及原始输入副本校验；A–I 对应源码、注册/物理列表/SD/TLS/ghost/材料与数值预检/动态门禁/收据链；三个既有 backend case；单次真实 20 事件的文件集合和哈希独立复算；冻结程序与 24 文件执行前后稳定性检查。网格贴边、别名、平移层级 true、跨 run 行为、缺失 TLS、动态负例等使用本轮通过的既有测试结果作为证据，未对所有测试中间文件另做保存和独立数值复算。

**未审**：H3-4 预注册 B/C Welch 统计判据、Case M 逐 worker 调度可重复性正式矩阵与独立复算；Linux/CI、GUI H3-3、复杂材料与输运的物理等效性、Stage B 专设失败注入。零命中时 hits 文件惰性缺席已由主审接受，受支持输入下不增加 Stage B 注入 hook，Case M 调度差异及真实物理验证留后续阶段。不能将现有正例测试描述为完整上游 Geant4 多线程模型的形式证明。

**建议**：本次限定复审结果可提交主审作 H3-2 r3 接受决策。H3-2 在主审签收前仍标记为待验收；H3-3 只能由主审后续派工。本轮未修改产品/测试源码、未提交、未构建、未联系 DeepSeek 或新建子任务。
