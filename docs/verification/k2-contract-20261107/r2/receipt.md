# K2-1 回执（合同修订 r2，待独审冻结）

- 任务：`docs/collab/decisions/20261107-k2-closeout.md` 的 K2-1（独立 Geant4 工程导出合同）。
- 本轮回执覆盖 **r2**：只按主审退回意见做四处最小修订并统一 staging 语义；r1 不回改、不覆盖。
- 时间（UTC）：2026-11-07T06:06:00Z。
- 工作树：HEAD `e44fb444c81aa8cd787b8ad23d106bb12344c4ab`（`roadmap/Q2-scientific-baselines`），102 项既有 dirty（均为任务前状态；ROADMAP/CURRENT 属监督端，本项只读）。
- 已执行：只读源码逐行核对 + 文档修订 + SHA 重算 + doc_links；**未**构建、**未**导出实际工程、**未**启动 Geant4、**未**改产品/GUI/CMake、**未**提交 Git。
- 冻结门禁：`ready_for_contract_review=true`（r2），停写等主审独审冻结。

## r1 保留（不覆盖）

r1 合同/参数/回执/闭包原样保留在 **主审独立快照目录** `out/collab/k2-contract-independent/r1/`（含 `identity.json` 与 16 个镜像文件）。本轮仅读取该目录，按 `identity.json` 重新核对 **16/16 文件 SHA 全部一致**，未改其中任何文件，也未新增/删除文件。

| r1 产物 | SHA-256 |
|---|---|
| 合同 r1 | `a02b4f8baf7b246caefc85b652c9fe846b3bf21fe629a7747030137159b70f4d` |
| parameters r1 | `b0b2bb35b84775f60d351dfa8103a3d1926b40c521692f7211a14f26091f45d7` |
| receipt r1 | `a562761e75e9585e8458f6a629face365749b11c1372a15b3d94d51f441051d0` |
| closure-files r1 | `c8e2a0b79cb4164fc6ea43d6cfda65ea2ac52f7c5fbadc9facd9ee2bc2fd9157` |

## r2 交付物（SHA-256）

| 文件 | r2 SHA-256 |
|---|---|
| `docs/collab/outbox/20261107-k2-contract.md`（454 行 / 45847 B） | `04fbabd5b420f98539ad716df3420f0f65307dab8205741d05e4bf98211d4212` |
| `out/collab/20261107-k2-contract/author/parameters.json`（r2） | `fa9a8efaede6b3e55dd16964ffb547224e04f20dde053911da8e0d1a603fa0b3` |
| `out/collab/20261107-k2-contract/author/closure-files.sha256`（未变，314 行） | `c8e2a0b79cb4164fc6ea43d6cfda65ea2ac52f7c5fbadc9facd9ee2bc2fd9157` |
| 本回执 | 见下一段报告（写后重算） |

## 实际核对源码行（r2 依据）

| 结论 | 证据 |
|---|---|
| `GetString` 原样返回字符串，不做相对路径解析 | `src/Config/ConfigManager.cc:165-172`：`return GetValue(section, key).AsString();` |
| 材料/几何路径按进程 cwd 直接 `IsFile` 后加载 | `src/Core/SimulationManager.cc:934-940`（materials）、`:955-960`（geometry） |
| 仅显式 `--working-directory` 才 chdir | `main.cc:642-655`（绝对路径校验→`is_directory`→`current_path`） |
| `scorer_statistics` 含随墙钟变化的列 | `src/Output/OutputManager.cc:289-298` 表头含 `fom_per_s`、`run_wall_time_s`；`:318-325` 写 `FigureOfMerit(relError, wallSeconds)` 与 `wallSeconds` |
| CTest 标签均为 `component`，`-R` 只能命中一个 | `CMakeLists.txt:135-140`（`h2_volume_scoring_check`，`LABELS "h2;component"`）、`:151-156`（`parallel_scoring_component`，`LABELS "h3;component"`） |

## r2 四处修订（其他内容未动）

1. **路径基准（§4.1/§4.2/§5.3 P7/P8）**：确认后端按 cwd 解析，主 INI 改写为 `project/config/...` 与 `runs/default/output`（均以导出根为基准）；运行命令必须先在导出根执行；新增毒化模板测试（P7）与搬移测试（P8），证明模板 config 不会被误读、目录移动后仍可执行；不改后端语义。
2. **CTest（§8.2/§8.3/§4.3 tests）**：改用 `ctest -L component` 并先断言 `Total Tests: 2` 且列出两个测试名；Windows 与 Linux 命令全部改为可直接复制的单行；manifest 字段改为 `component_ctest_label`/`component_ctest_expected=2`。
3. **模板身份（§3.3/§4.3/§5.2 R11/§5.3 P4/§9.1/§11/附录 A、C）**：`1862a858…`（308 文件）与 `c8e2a0b7…`（314 文件）降级为**历史基线**，不再作为导出冻结身份；冻结集合规则 + `packaging/export_template_manifest.json` + 身份绑定流程；K2-2 冻结新身份，开发与打包必须相等；禁止硬编码旧 digest，正常模板变更不重开合同。
4. **物理输出比较（§7.2 观察量 4、§8.4 确定性）**：纯科学 CSV 逐字节一致；`scorer_statistics` 排除 `run_wall_time_s`/`fom_per_s` 两列后其余字段/行数/行序严格一致（无新增容差，完整 SHA 只登记）；`run_summary`/metadata/`execution_id`/绝对路径/时间日志只登记不判等。
5. **staging 矛盾统一（§4.2/§5.2 R7/附录 D）**：任何失败一律清理 staging，诊断写独立证据目录，不残留半成品。

## 未实现/未验证（明确）

导出器、模板构建器、manifest、GUI/CLI 入口、CMake standalone 开关、打包 `export-template/`、两平台独立构建/运行/受控修改、正式回归与云 CI 均为**未实现/未验证**（K2-2/K2-3/K2-4）；本轮不主张任何实现完成。

## 停止状态

`ready_for_contract_review=true`；等待主审独审冻结后进入 K2-2。未运行任何 Geant4 或构建命令，未导出工程，未提交 Git。

---

## r2 补充（2026-11-07，主审 m26737：web 快照独审与 S-B/P3/CTest 定位）

已读 `out/collab/k2-contract-independent/r1/web-review.md`：其四项 P0/P1 与主审意见一致，并额外指出 P3 与 S-B 随机 staging 审计路径矛盾。本轮只同步合同/parameters/receipt，不构建、不导出、不运行、不改产品。

1. **S-B 流程固定**：现有 `package_writer.py:158-175` 对全部 package 字段 `.resolve()`，`main_ini_writer.py:129/132/136` 原样写绝对 `dir/file/config`。合同 §4.2 不再声称 writer 支持相对路径，也不改 writer；导出器在隔离 staging 原样生成后，只对白名单键（`[materials]/file`、`[geometry]/config`、可选 `[parallel_world]/geometry_config`、可选 `[run]/macro`、`[output]/dir`）重写为导出根相对值，再静态扫描与闭包核验。
2. **manifest 生成输入**：`inputs[].original_path` 对生成输入固定为 `generated:<logical-name>`（main/materials/geometry/run/可选 parallel），随机 staging 路径与每次不同的临时目录名不得进入 manifest 任何字段；opened_project 仍记原项目绝对路径。
3. **P3 口径**：同一输入两次导出到不同 destination，内容 identity（排除 `export-manifest.json`）逐字节一致且 digest 相等；manifest 仅允许 `created_utc` 一个字段不同，其它字段逐字段相等；不把 manifest 逐字节相同当判据，也不登记其它可变字段。
4. **CTest 定位**：改用 `ctest -L "^component$"`，先断言 `Total Tests: 2` 且测试名集合恰为 `{h2_volume_scoring_check, parallel_scoring_component}`，再要求通过；仅断言数量视为失败。

**保留证据**：r1 快照由主审保管在 `out/collab/k2-contract-independent/r1/`（`identity.json` 16 个文件 SHA 复核一致，未改动）；本次补充前的 r2 草稿完整保存在 `out/collab/20261107-k2-contract/author/drafts/r2-pre-supplement/`（contract `04fbabd5…`、parameters `fa9a8efa…`、receipt `024681e4…`）。

**校验**：合同 457 行 / 50,038 B / SHA-256 `e27f5a81c83b7af554a0097e4a96ccc0965cdbe3872ccec7dd5f859697931b4f`；`python -B scripts/check_doc_links.py` 与 git 状态见本次回执末尾；最终四项 SHA 见同目录 `checksums-r2.txt`。

## r2 补充校验（实际执行，2026-11-07）

- 合同：457 行 / 50,038 B / SHA-256 `e27f5a81c83b7af554a0097e4a96ccc0965cdbe3872ccec7dd5f859697931b4f`。
- `python -B scripts/check_doc_links.py`：1496 relative links / 513 files / 0 broken。
- `python -B out/patch_contract_r2_supplement.py`：13 处唯一命中替换全部成功（S-B、manifest、P2/P3/P5、Windows/Linux CTest、§9.1、§11、header）；追加核对发现附录验收表 P5 行仍写 `ctest -L component`，已同步改为 `-L "^component$"` + 精确名称断言（同属 r2 补充，不扩范围）。
- r1 快照 `out/collab/k2-contract-independent/r1/`：`identity.json` 与 16 个文件 SHA 复核一致，未改动。
- r2 补前草稿：`author/drafts/r2-pre-supplement/`（contract `04fbabd5…`、parameters `fa9a8efa…`、receipt `024681e4…`）。
- 未构建、未导出实际工程、未启动 Geant4、未改产品代码/CPP/CMake、未提交 Git；HEAD `e44fb444`。
- 本回执与 parameters.json 的最终 SHA 记录在同目录 `checksums-r2.txt`（回执无法自引用自身 SHA）。
