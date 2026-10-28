# Changelog

Short, user-facing record of notable changes. Detailed support status lives in
`docs/功能支持矩阵.md`; the roadmap and phase status live in `docs/ROADMAP.md`.

## Unreleased

### Added

- 测试平台报告 v2：每个用例经 `tools/test_assert_probe.py` 记录已执行 `assert` 数（`G4USIM_ASSERTS` marker），报告新增 `tests_content_fingerprint`、逐用例 `assert_sites`/`assertions_executed`/`log_sha256`；新增 `scripts/check_report_evidence.py` 作为 CI 证据门禁，`scripts/test_report_evidence.py`（static）覆盖其拒绝路径。
- 测试平台 `--fail-on-skip`：CI 的 static/gui 步骤不再让缺失 Qt/uproot/后端的 skip 以退出码 2 变绿；`--report-root` 默认改为 `out/verification`。
- 支持矩阵第 2–3 节每条功能的事实列末尾标注证据类型（外部表 / 解析式 / 同源自洽 / 自测 / 未验证），并在第 1 节给出判定口径；`.gitattributes` 对 `docs/verification/**` 关闭换行归一，证据副本与生成产物保持字节一致。
- 九个零断言用例改为 `assert` 表达（`config_schema`、`geometry_safety`、`gui_backend_agreement`、`material_schema`、`gui_sketch_accuracy`、`unsupported_features`、`unconsumed_config`、`benchmarks`），`report.json` 的 `cases_with_zero_assertions` 现在为空数组。
- `scripts/check_report_evidence.py` 新增 `--baseline`（断言总数、逐项计数、用例集合不下降）、`--allow-legacy-digest`/`--allow-legacy-probe`（仅用于复核归档报告）、`--allow-incomplete`（仅用于排查），并让 CI 的 static/gui 两个步骤各自跑完后分别过门禁。
- 新增 static 用例 `writer_boundary`（`scripts/test_writer_boundary.py`）：把 Astra E2-S1 的六个 editor→writer 边界（非有限能量、非有限半径、零半径、非有限截断、直方图上下限倒置）从被忽略的临时探针提升为正式回归。
- 断言探针升级为 `settrace_assert_lines_v2`：同时安装 `threading.settrace`，脚本自己启动的线程里执行的 `assert` 也计入 `G4USIM_ASSERTS`。

### Fixed

- 交互偏置拒绝只是 `JustWarning`（Astra 2026-10-28 审查 D-4）：`/AIHL/biasing/*` 修改类命令在 `--ui --ui-session csh` 下被拒绝后，会话继续、`/run/beamOn` 照常执行、进程退出 0，用户以为配置了偏置但物理未偏置。现在 `BiasingManager` 记录拒绝次数，`main.cc` 在会话后把 `biasing` 计入交互失败、停止会话、写 `status=failed` 与非零退出。
- 初始化后的材料修改无生命周期门禁（Astra 2026-10-28 审查 D-5）：`/AIHL/material/*` 的 9 个修改命令现在只在 `PreInit` 可用（只读 `print`/`list` 不变），交互会话内初始化后调用会被 Geant4 拒绝并让会话失败（`geant4_illegal_application_state`），batch 路径的守卫保留。
- `ParseStrictDouble` 不检查有限性（Astra 2026-10-28 审查 D-6）：`inf`/`nan`/溢出值现在报 `Config value '<v>' is not a finite double` 并在创建 Geant4 对象前失败。
- 证据门禁可被篡改绕过（Astra 2026-10-28 审查 D-1）：`scripts/check_report_evidence.py` 现在校验逐用例断言 ≥ 1、`exit_code == 0`、逐项求和与总数一致、`cases_with_assertion_counts`/`cases_with_zero_assertions` 与实际记录一致、`log_sha256` 与磁盘日志字节一致、发布报告无 fail/skip，并支持 `--baseline` 校验不下降；实测"把通过项断言改成 0""把日志摘要换成 0 并放大总数"两种篡改均被拒绝。
- 日志摘要与磁盘字节不符（Astra 2026-10-28 审查 D-2）：`scripts/run_m0_tests.py` 改为写 UTF-8/LF 字节并对落盘字节计算 SHA-256（`log_digest_algorithm=sha256_raw_bytes_lf_v2`），`report.json` 同样按字节写出；此前 Windows 文本模式写 CRLF、摘要却算 LF 字符串，归档的 79 个日志原始字节 0/79 可复现。
- `.gitattributes` 的 `* text=auto` 导致 Windows 检出写入 CRLF，使按原始字节哈希的工作区指纹漂移、backend 用例全部 SKIP；现对 `*.cc`/`*.hh`/`*.h`/`*.in`/`*.py`/`*.json`/`*.ini`/`*.mac`/`*.csv` 与 `CMakeLists.txt` 固定 `text eol=lf`，并重新物化受影响的跟踪文件。
- `scripts/test_config_duplicate_declarations.py`、`scripts/test_command_state_gating.py` 的验证 helper 改用 `assert` 表达，使断言级证据可被探针计数（此前 `raise AssertionError` 对探针不可见）。
- `scripts/run_benchmarks.py` 的断言从逐基准循环内移到 `write_report()` 之后：原先位置在单个基准失败时会中止后续基准并跳过报告写出，属于行为回归。

### Changed
- **状态入口收敛**：新增仓库根 `STATUS.md` 作为当前快照/阶段进度/证据/已知缺口的唯一入口；`docs/ROADMAP.md` 是阶段状态唯一登记处；5 份带日期的过期状态文档（`持续开发执行规划`、`当前开发交接`、`开发审计与阶段目标`、`M0-接续检查点`、`M0-M5-原型推进看板`）移入 `docs/archive/` 并加归档说明与索引。
- **AGENTS.md 瘦身**：29 条逐日实施契约全文迁入 `docs/agent-history.md`，`AGENTS.md` 只保留规则与一行式索引（48.5 KB → 33.5 KB）。
- **文档反向错误修复**：`README.md` 与 `docs/中文使用手册.md` 不再声称 LET/GDML/STL/自动合并未实现（这些能力早已存在，只是实验性或部分支持）；`CHANGELOG.md` 头部不再指向外部 claude.ai 项目。

### Added
- **static 用例 `doc_links`**：`scripts/check_doc_links.py` 校验仓库内 Markdown 相对链接与图片路径存在（跳过代码块、外链与锚点，支持 `file.cc:123` 与仓库内绝对路径），当前 50 个文件 76 条链接 0 断链；用例总数 77。
### Added
- **多模型协作试运行**：新增协作约定与 E2 独立审计记录；当前 4 项专项及 7 个临时 writer 边界检查通过，未发现可确认功能缺陷。保留一项正式回归补强建议；没有修改生产代码或启动 F6。
- **E2 配置 schema 接续**：源（含高级 GPS/多源/相空间）、物理、计分、六种几何模板和材料文件进入统一字段登记；生成逐字段解析入口/校验阶段/GUI范围/测试覆盖清单。保留上下文及运行时校验、历史警告与元数据行为；field/biasing 不在本次迁移内。GUI 当前生成字段复用标量约束，停止输出未消费的 physics.mode；未开放高级编辑器。实现提交 aaa9c1d；70 项完整回归与最后 4 项专项通过。详见 docs/配置schema说明.md。

- **Configuration schema** (roadmap E2, first modules `[run]`, `[general]`, `[output]`):
  `schema/config_schema.json` describes each field (type, limits, allowed values,
  aliases, default, what an empty value means, support level, since, description in
  English and Chinese). `scripts/generate_config_schema.py` generates the backend's key
  table (`include/Config/ConfigSchemaTable.hh`, used by the unknown-field warnings), the
  GUI's validator data and the field tables in `docs/功能支持矩阵.md` (section 5). The
  GUI checks run settings and trajectory events with it, and the controls' tooltips are
  its hints. `scripts/test_config_schema.py` runs 255 values through both the GUI check
  and the backend (`--inspect-run`) and checks that every field and alias is read,
  unknown keys are reported, and defaults and alias precedence are as described.
- **Accurate editor sketch** (roadmap G4). The sketch places each volume inside its parent
  the way Geant4 does (`G4PVPlacement`: positions relative to the mother, rotations X then
  Y then Z of the frame, unitless angles in radians) and draws every backend solid with
  its phi/theta segments: box, tubs, cons, sphere, orb, trd, trap, ellipsoid, eltube,
  torus, para, hype, polycone, polyhedra and STL files. What it cannot draw (replica and
  parameterised copies, boolean results) is listed with the reason. The bounding box of
  every volume matches the mesh Geant4 builds for all repository geometry files and
  three written fixtures (`scripts/test_sketch_accuracy.py`, 130 volumes).
- **Source display** (roadmap G5): the 3D view draws the source as GPS samples it: a dot
  for a point source, the disc or rectangle of a plane source in the XY plane, an arrow
  for a fixed direction (with parallel arrows from the plane's edge), rays in all
  directions for isotropic emission, and a cone, a hemisphere or a focus arrow for the
  preview-only modes (drawn faint and marked "preview only"). The source is drawn over the
  Geant4 geometry as well (in generated mode) and described below the view. Checked
  against real primaries: 4 sources x 200 geantinos start inside their glyphs and leave
  along the drawn directions (`gui/smoke_tests/smoke_source_glyphs.py`).
- **Particle tracks in the 3D view** (roadmap G6). Run Config > Scoring has "Particle
  tracks of the first events" (writes `[output] trajectories = N`); after such a run the
  3D view overlays its tracks, or **Load Tracks...** reads any run folder. Each particle
  has a fixed colour with a legend whose check boxes hide it; one event at a time with
  previous/next or all events; "Primaries only" and a minimum starting energy for
  secondaries. Volumes turn to faint glass while tracks are shown.
- **Particle trajectories** (roadmap H1): `[output] trajectories = N` writes every track
  of events 0..N-1 per worker to `trajectories_tN[_rR].json` (schema
  `g4usim_trajectories_v1`: particle, parent, creator and end process, initial energy,
  length, and per-step end points with kinetic energy and the volume of each segment);
  `trajectory_min_energy` drops low-energy secondaries, `trajectory_max_points` caps a
  file. Checked by `scripts/test_trajectories.py`: segments lie in their volumes,
  primary lengths equal the hits file's step sums, and the mean primary path of 100 MeV
  protons in water agrees with the PSTAR CSDA range (+0.58 %).

### Changed
- **GUI code split by editor** (roadmap E5): the Configuration page (2,400 lines) is now
  `widgets/config/` with one widget per editor (setup column, Materials, Geometry, 3D
  Preview, Run Config, Messages and files) plus that editor's logic (also layers and
  boolean operations), and the main window (1,000 lines) is split into
  `window/shell.py`, `project.py`, `run.py` and `content.py`. A fingerprint of every
  widget, text, placement and signal connection is unchanged apart from the fix below.
- **3D view redesign** (roadmap G2/G3): one colour per material (common materials keep
  fixed colours) with a legend whose check boxes hide a material; the world hidden by
  default; volumes that contain others drawn as faint glass; theme background; camera
  presets (front, side, top, iso) and an orthographic toggle; hovering a volume names
  it with material, solid and volume; a click selects it (and its row in the volume
  table, both ways) and fades the rest; Isolate, Hide and Show all; a section plane
  along x, y or z with a slider. The same view draws the Geant4 world and the editor
  sketch. Permanent labels are now off by default (hover replaces them).
- **The 3D view shows the real Geant4 geometry by default** (roadmap G1). Opening the 3D
  Preview tab builds the world with the backend (about 3 s) without generating a run
  package first, and rebuilds it a moment after each change while the tab is open
  (option "Geant4 geometry automatically"). The editor sketch is shown, labelled
  approximate, while Geant4 builds; unchanged geometry is shown from a cache; a burst of
  edits ends in one export of the latest state; failures show the backend's own reason.
  Unedited geometry and materials files are used in place, so files they refer to (STL,
  GDML) keep resolving.

### Fixed
- **位移损伤粒子名（2026-10-27 B1）**：`[scoring.displacement]` 的键被 INI 读取器转成小写，旧实现按小写查表，导致 `he3` 一类名字永远不匹配、DDD 静默为 0 且退出码 0。现在按 Geant4 粒子表大小写不敏感解析为规范名（`he3` → `He3`），不匹配任何粒子时在首个事件前失败，并报出主 INI 文件、行号和候选。
- **主 INI 重复声明（2026-10-27 B2）**：同一 section 或同一 key 重复声明此前被静默覆盖。现在输出 `[ConfigWarning] duplicate declaration <file>:<line> [<section>]/<key> = <value>` 并在摘要记录 `config_duplicate_count`；实际生效值仍是最后一次声明（兼容行为不变）。几何文件 `version = 2` 的严格拒绝与此独立。
- **命令状态门禁（2026-10-27 B3/B4）**：`/AIHL/detector/enableSD`、`/AIHL/detector/setSDName`、`/AIHL/app/setSeed` 在 `/run/initialize` 之后只打印 warning 并改动 Manager 缓存，Geant4 内核仍用旧状态而进程返回 0。三条命令现在只在 `PreInit` 可用，非法状态使 batch 失败、写 `status=failed` 摘要并非零退出。敏感探测器改为按配置的探测器名创建（原先硬编码 `AIHLParticleSD`，改名后会重复注册）。
- **GUI 源字段保留（2026-10-27）**：在 Setup 栏修改源粒子/能量/预设或计分选项时，GUI 会把已配置的平面/矩形/各向同性源静默重置为点源 + 固定束流，生成的 main.ini 随之丢字段而运行仍“成功”。现在源几何只由 Source editor 决定，Setup 栏只镜像它真正暴露的标量字段。
- **GUI 进度与日志（2026-10-27）**：进度终态不再显示“进度已冻结”，改用“结果：模拟成功／用户停止／强制结束／结果未证实”；stdout/stderr/merged 三个日志视图加行数上限，merged 前缀只在行首插入，GUI 与 runner 的日志解析都按完整行跨 chunk 缓冲（同时修掉 `[gui] [gui]` 双前缀）。
- Integer fields above 2147483647 (for example `seed = 99999999999`) were silently clamped
  to 2147483647 on Windows; they are now rejected as out of range.
- The GUI accepted a negative seed or one above 2147483647, which the backend rejects or
  clamped; it now checks the seed as the backend does.
- The editor sketch placed every volume as if its position were absolute (daughters of
  a moved or rotated mother were in the wrong place) and turned rotated volumes the
  wrong way; partial tubs, cones and spheres were drawn whole.
- The plane source was drawn tilted by the editor's normal, but Geant4 always samples it
  in the XY plane; the normal is now ignored with a warning, as in the backend.
- Polycone, polyhedra and STL keys (`z_planes`, `r_inner`, `r_outer`, `file`,
  `file_unit`) and replica/parameterised keys were reported as legacy metadata.
- "Show Source" and "Show Labels" take effect at once instead of marking the view stale.
- The Configuration tabs overlapped when the window was smaller than they need (the
  Materials table ran under the "Selected material" box, toolbar buttons were clipped):
  the editors now scroll, long status lines wrap, the Materials toolbar has two rows and
  the source-copy check box is shorter ("Copy the original geometry file", details in its
  tooltip).
- The Geometry tab's **Add Volume** also added a volume-fraction material, and the Materials
  tab had no **Add volume_fraction** button: both used one shared attribute. They are
  separate buttons again.
- Writing the generated-geometry preview no longer erases the Geometry Editor's material
  errors (the writer re-validated the document in place with every referenced material
  counted as defined).
- **GUI checks now match the backend for geometry and materials** (roadmap E1). The
  default demo project could not generate a package or show backend geometry: the GUI
  compared material names case-sensitively and paired the demo geometry with a
  materials file without `iron`. Also fixed in the GUI: `[material.X]` read as a
  material named `material.X`, `[element.*]`/`[isotope.*]`/`[NIST]` sections read as
  materials (and dropped from generated materials files), component counts and
  fractions lost when a materials file was loaded, volume-fraction materials without a
  density rejected (the backend uses `auto`), circular material definitions accepted,
  and backend-supported shapes outside the editor (trap, torus, polycone, ...) reported
  as invalid instead of pointing to source copy mode.

### Added
- `scripts/test_gui_backend_agreement.py` (suite case `gui_backend_agreement`): every
  geometry/material fixture, the repository's main INIs and the wizard scenarios go
  through both the GUI validators and the backend (Geant4 initialisation plus mesh
  export); any disagreement fails, and the GUI writers' output must also be accepted.
- **GUI refresh and examples gallery**: a Start page (new simulation, open project, recent
  projects) with five examples that open with results Geant4 already computed (proton
  Bragg peak, shielding slab, silicon Landau distribution, NaI gamma spectrum, proton
  energy scan; bundled under `examples/gallery/`, regenerated by
  `examples/gallery/build_gallery.py`). New line-icon set, refined light/dark palette
  (also applied to the Qt palette, so check boxes, arrows and table headers follow the
  theme), status chips, icon-only Theme/Language buttons, version in the sidebar,
  collapsible setup sections on Configuration, grouped tabs on Configuration and
  Results, theme-coloured plots with their own toolbar, empty states for plots and the
  3D view, scenario icons in the wizard. Fixes: validation and volume count stale after
  the wizard, plots not following the theme, untranslated scan headers, an empty scan
  parameter list until the page was refreshed, Chinese text in plots, `.root` files
  shown as "unknown". Moved or bundled scans reopen with paths relative to `scan.json`.
- **Windows installer** (roadmap Phase D): `packaging/build_package.py` builds a portable
  folder, a ZIP and an Inno Setup installer with the backend and its DLLs, a frozen GUI
  (no Python needed), examples, scenarios, scripts, docs and third-party licenses. The
  Geant4 data is not bundled; the backend finds an existing data folder through the usual
  variables, `GEANT4_DATA_DIR` or `bin/geant4-data.txt`, and the new
  `--check-geant4-data` option reports what it found. The GUI gains `--self-test`.
- **Parameter scans and batch runs** (roadmap Phase C3): a Parameter Scans page varies
  one Configuration-page setting (source energy or particle, physics list, seed, events,
  a volume's material or box thickness) over a list or lin/log range, writes one run
  package per point plus `scan.json`, runs the points one after another and shows a
  results table and a plot of any scorer quantity with statistical errors.
- **New simulation wizard** (roadmap Phase C2): File -> New Simulation... guides through
  scenario (single target, depth-dose phantom, shielding slab, silicon detector, gamma
  spectrometer), NIST materials and sizes, source, and physics/outputs/run, then fills
  the Configuration page's editors and can generate the package and run right away.
- **Built-in plots** (roadmap Phase C1): a Results / Plots tab in the GUI for scorer
  totals with statistical error bars, scoring-mesh depth profiles and 2D maps (CSV or
  ROOT), Edep histograms, per-event deposit and phase-space spectra, with log axes,
  per-primary normalisation, run overlay, comparison across output directories and
  image/CSV export. `gui/requirements.txt` now lists numpy and matplotlib.
- **Detector response pack** (roadmap Phase B4): `scenarios/detector_response/` with
  `make_detector.py` (housed gamma spectrometer crystals, silicon pads) and
  `analyze_detector.py` (pulse-height spectra, Gaussian resolution, efficiencies,
  peak-to-total, Compton edge, escape peaks, most probable deposit). New benchmark
  `detector_response` (Klein-Nishina Compton edges, pair escape lines, PDG
  Landau-Vavilov-Bichsel most probable energy loss in silicon).
- **Semiconductor device pack** (roadmap Phase B3): `scenarios/semiconductor/` with
  `make_device.py` (lid, BEOL, gate oxide, active silicon, substrate depth slices) and
  `analyze_device.py` (per-layer TID, displacement damage dose, 1 MeV neutron-equivalent
  fluence, depth profile); SR-NIEL silicon NIEL tables for protons, electrons and
  neutrons (ASTM E722-19) with a converter. New benchmark `device_dose` (thin-slab proton
  dose vs NIST PSTAR silicon stopping power; DDD vs the SR-NIEL tables).
- **Shielding / coating scenario pack** (roadmap Phase B2): `scenarios/shielding_coating/`
  ports CoatingSimulation as `make_scenario.py` (layer stack, mission spectra, mixed
  sources, junction layers, vacuum pores, transmission/albedo spectra) and `analyze.py`
  (TID, DDD, spectra). New experimental **displacement damage dose** scorer:
  `[scoring] displacement = true` with `[scoring.displacement] <particle> = <NIEL table>`
  writes `displacement_volume_summary_tN[_rR].csv` and `ddd_*` statistics. New benchmark
  `shielding_range` (Al/Si CSDA ranges and proton residual energies vs NIST PSTAR/ESTAR).
- **Physics benchmarks** (roadmap Phase B1): `scenarios/benchmarks/` packs (reference
  data, runnable example configs, Chinese READMEs) for water CSDA ranges (NIST
  PSTAR/ESTAR), the 150 MeV proton Bragg peak R80, and narrow-beam photon attenuation
  (NIST XCOM); `scripts/run_benchmarks.py` runs them and writes a JSON/Markdown report
  (`--quick` runs in the test suite).
- **Electromagnetic fields** (roadmap A7, experimental): `[field]` (global) and
  `[field.<name>]` with `volumes` (local) take uniform `magnetic` / `electric` values
  (combined fields allowed) or `magnetic_map` / `electric_map` CSV grids with trilinear
  interpolation, plus `min_step` / `delta_chord` / `delta_one_step` /
  `delta_intersection`. `scripts/test_fields_a7.py` checks trajectories against exact
  analytic results (circle in B, work done by E, Wien filter, canonical momentum in a
  gradient map, local field box).
- **Physics options** (roadmap A6, experimental): `[physics.region.<name>]` production
  cuts, `max_step`, `max_track_length`, `max_time`, `min_kinetic_energy` and `volumes`
  (regions can be created from logical volumes, also for GDML); `/AIHL/physics/setRegionCut`
  now works; `[physics.radioactive_decay] enabled / time_threshold` (Geant4's default
  1-year threshold skips long-lived nuclides such as Co-60); `/AIHL/physics/dumpProcesses`
  writes processes, models, region cuts/limits and energy thresholds as JSON. Time values
  accept `min`, `h`, `d`, `y`. `scripts/test_physics_a6.py` checks the EM presets against
  NIST XCOM and the decay settings against NNDC.
- **Geometry** (roadmap A5, experimental): new solids `ellipsoid`, `eltube`, `torus`,
  `para`, `hype`, `polycone`, `polyhedra`; STL import as `shape = tessellated` (ASCII or
  binary, closed-manifold check, automatic reorientation); `placement = replica` (box
  x/y/z, tubs phi) and `placement = parameterised` (per-copy position, rotation and
  material from `copies_file`, or `copies` + `copy_step`); `/AIHL/geometry/exportMesh`
  writes the geometry Geant4 actually built (`g4usim_geometry_mesh_v1`) and the GUI 3D
  Preview gains "Show Backend Geometry". `scripts/test_geometry_a5.py` checks volumes
  against analytic formulas, exact STL navigation, replica dose against explicit slabs
  and per-copy materials.
- **GDML** (roadmap A5): `[geometry] template = gdml` imports a GDML file through
  `G4GDMLParser` (`[gdml] file`, `validate`, `sensitive_volumes`, `bias_volumes`, and
  `<auxiliary auxtype="SensDet">`); `/AIHL/geometry/exportGDML` writes the built world.
  Needs Geant4 with GDML; the backend reports it in `--capabilities`.
- `--capabilities` now lists the A4 source modes, A5 solids and placements, and the
  ROOT schema version 4 (it still reported the pre-A3/A4 state).
- **Full GPS sources** (roadmap A4, experimental): energy spectra (`energy_type` gauss,
  uniform, power, exp, histogram or point-wise `spectrum_file`), volume sources (sphere,
  cylinder, box, ellipsoid) with `confine`, Gaussian beam spots, rotated planes
  (`rot1`/`rot2`), annulus/ellipse/square planes, angular distributions (cosine law, cone,
  beam1d, beam2d, focused), multiple weighted sources in `[source.<name>]` sections, ion
  and radioactive-decay sources (`particle = ion`, `ion = Z A [Q [E*]]`), and phase-space
  files: `[phase_space]` writes particles entering a volume to `phase_space_tN[_rR].csv`
  and `[source] phase_space_file` replays them (event k = history k).
  `scripts/test_gps_sources.py` checks every distribution against analytic expectations
  from real primary vertices, Na-24 decay against NNDC, and exact phase-space replay.
- **Statistical uncertainty for every built-in scorer** (roadmap A3): Edep (event total,
  per volume, per particle), Dose, Fluence and LET now accumulate per-event sums of
  squares. The master writes the merged `scorer_statistics[_rR].csv` (any output format)
  with value, mean per event, standard error, relative error and figure of merit; LET_t /
  LET_d use delta-method errors for ratios. Per-thread CSVs and ROOT ntuples gain additive
  `*_sum_sq*` and `n_events` columns (ROOT schema `g4usim_root_v4`; dose/fluence/LET CSV v2,
  edep summary CSV v4); `scripts/g4usim_io.py` adds `load_scorer_statistics()`.
  `scripts/test_statistical_uncertainty.py` checks against raw hits and against the
  observed spread of 20 independent runs.
- **Geant4 scoring meshes** (roadmap A2): native `/score/` box and cylinder meshes with
  all primitive scorers and particle/energy filters, from macros or INI
  (`[scoring.mesh.<mesh>]`, `[scoring.mesh.<mesh>.<quantity>]`). Results per run in the
  ROOT `mesh` ntuple and `scoring_mesh[_rR].csv` with sum, sum of squares, entries and
  relative error; `scripts/g4usim_io.py` loads them as dense arrays.
- **LET** (roadmap A2): `[scoring] let = true` gives track- and dose-averaged LET per
  sensitive volume (`let` ntuple, `let_volume_summary` CSV), checked against the Bethe
  formula for protons in water.
- Dose and fluence prototypes validated against native `doseDeposit` / `cellFlux`
  (agreement < 1e-9).
- ROOT schema is now `g4usim_root_v3` (adds `mesh` and `let`).
- **ROOT output** via Geant4 `G4AnalysisManager` (roadmap Phase A1).
  `[output] format = csv | root | both` and `/AIHL/output/setFormat`.
  One `g4usim.root` per run with worker threads merged automatically; histograms
  `edep_raw`, `edep_weighted`; ntuples `hits`, `events`, `edep_volume`,
  `edep_particle`, `dose`, `fluence` (schema `g4usim_root_v1`).
- `run_metadata.json`: machine-readable run summary (format, Geant4 version,
  source fingerprint, runs, generated files with schemas).
- `scripts/compare_root_csv.py` and the `root_output` regression case.

### Changed
- `scripts/run_m0_tests.py` no longer crashes when a failing case's log tail contains
  characters the console code page cannot encode (they are replaced).
- Repository hygiene: corrected `.gitignore`, removed tracked build artifacts and
  Geant4 example B1 leftovers, `.gitattributes` line-ending normalization.
- `gui/requirements.txt` now includes `uproot`.
