# H3-2 lifecycle / overlap fix r3 — delivery receipt

- 日期：2026-11-07
- 基线：H3-2 fix-r2 交付（材料证明 unknown 修复，回执 `docs/collab/outbox/20261107-h3-material-proof-fix-r2.md`）
- 依据：`docs/collab/reviews/20261107-h3-backend-fix-r2-independent-web.md`；主审核验 `out/collab/h3-independent-r3/supervisor-additional-verified.json`
- 结论：只修该复审里两个已实证点，全部范围内项完成；未扩展覆盖，未改统计/物理判据，停写等复审。

## 修了什么

### 1. 材料证明与当前质量几何绑定（原 B/E 生命周期）

根因：一致性证明只在 `Configure()` 计算。随后 PreInit 宏执行
`/AIHL/geometry/loadConfig geometry_copper.ini` 把质量几何整体替换，`GeometryManager` 树已变，
但证明与有效配置仍是 water 树的旧结论，因此 20 事件真实 copper 运行里仍显示
`material_matches_mass_world = true`。

修复（产品 diff 见 `r3-product.diff`）：

- `ParallelWorldConfig::RebindToCurrentGeometry(geometry, materials)`：重新做声明包含检查、
  材料解析、密度/参考质量计算，并**重置后重新推导**每个体积的整盒材料证明；证明不可重复时为
  `unknown`，不继承 `true`。当前几何无法容纳声明体积/材料无法解析时抛错，走既有失败通道。
- `SimulationManager::RefreshParallelWorldForCurrentGeometry()`：调用 rebind 后刷新有效配置；
  在 (a) `ConfirmEffectiveCommand()` 处理 `/AIHL/geometry/*` 成功后立即调用；
  (b) `ValidateParallelWorldForRun()` 在 `/run/initialize` 与运行前调用。
  入口覆盖 batch / csh / 受控 session；不新增命令，不改既有 PreInit 语义。
- 重绑入口先复用既有 `ValidateMainName(name_, geometry)`（主审补充要求）：PreInit 换几何可能
  换掉 world 名，原 Load 时“并行世界名不得与质量世界名冲突”的拒绝必须在 live 树上继续成立。
  该检查只针对 parallel world 自身 `name`，并行/质量体积同名的既有允许语义不变，不新增规则。

### 2. 内部交叠的浮点误差界限（原 A）

根因：内部交叠用 `1e-9 × max(1, |low|, |high|)` 相对容差。世界坐标 1,000,000 mm 处
容差约 0.001 mm，把 0.0005 mm 的真实交叠当成接触接受，违反“严格正体积交叠拒绝”。

修复：改用可解释的绝对误差界

```
CoordinateBound(a, b) = 64 * DBL_EPSILON * (|a| + |b| + 1)
```

用于展开体积内部交叠、声明包含、整盒包含、异材质后代内部相交四处判定；面/边/点接触与合法
规则网格仍通过。1,000,000 mm 处界约 2.8e-8 mm，远小于 0.0005 mm。

## 验证（全部通过）

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 现象 1 精确回归 | `python -B scripts/test_parallel_world.py` | `test_parallel_world: OK`（内嵌 review 原始字节 + SHA 核对；20 事件完成、copper/water、`unknown`） |
| 现象 2 精确回归 | 同上 | 同一用例内 `--dry-run` 非零退出，`overlap in their interior` |
| 手工复演（当前 exe） | `repro/lifecycle-geometry-switch`、`repro/overlap-precision-repro` | exit 0（20 事件 completed）/ exit 1（构造前拒绝） |
| 组件检查 | `build_vs2026/Release/parallelScoringCheck.exe` | 21 项 PASS |
| CTest | `ctest -C Release -R parallel_scoring_component` | Passed |
| 定向回归 | `python -B scripts/test_run_summary.py` | M0-2 run summary regression tests passed（重绑入口补名检查后重跑） |
| 链接 | `python -B scripts/check_doc_links.py` | 1463 links / 453 files / 0 broken |

- 已验正例（同材料无旋转叶盒、别名、平移层级）与 r2 材料 `unknown` 反例保持通过；Stage A/E
  拒绝矩阵不变。
- 未跑 H3-4 统计批次、未跑 Linux/CI、未改 GUI/H3-4/ROADMAP/CURRENT。

## 证据与身份

- 证据目录：`out/collab/20261107-h3-lifecycle-overlap-r3/`
  - `r3-product.diff` SHA-256 `733b2071812ac42356a2483ae1284fe0ac7114510c6f53e43d89bfe87e685597`（5 文件 +89/-8，含重绑入口的 ValidateMainName 复用）
  - `r3-test.diff` SHA-256 `a6d920447fa4ebb64d08fac79128af978d45acbb099c6e886a863afcee581959`（1 文件 +60/-1）
  - `identities.json`、`r2-base/`（反推得到的 r2 交付文本，用于生成最小 diff）、`repro/`、
    `logs/`、`evidence-cases/`、`README.md`
  - 回归输入原始字节：`out/collab/h3-independent-r3/` 原目录保留；复演副本在 `repro/`，
    测试脚本内嵌同一字节与 SHA-256，写盘前逐个核对
- 构建身份：HEAD `83c0b1399584031f82d7d1fe38443ed2d1713e4f`（`git_dirty = true`，含任务前既有 supervisor 修改）；
  exe SHA-256 `14b9f29e7b71bac9beb1c582582c7deeab3e27d73faae958ee46d083fcd09537`；组件 exe SHA-256 `2525be0a3e8ed4d1c0ed15f0ce412b069bf64aecfc548798b712e0645c6c1eb2`；
  `source_fingerprint = 860b54b2982f1d50d2d414b74eb21864243250874d7a4770a1b4a94245dff114`；MSVC Release，Geant4 11.3.2。
- 构建命令：
  `env -u no_proxy -u http_proxy -u https_proxy -u ALL_PROXY cmake --build build_vs2026 --config Release --target G4UniversalSim parallelScoringCheck`
- 文档：`docs/并行世界计分.md` §10（生命周期重绑、浮点交叠界限、回归与边界；SHA-256 `ff77c8be62cf0d2de64e3f3c85779c4977156579e1ce341570e2f91b8a66f41c`）；
  测试脚本 `scripts/test_parallel_world.py` SHA-256 `d7762af097d1c682c6456a05c48e083697c556f718928427d6047d89631b562b`。
- 未提交 Git；工作区仍有任务前既有改动（`M docs/ROADMAP.md`、`M docs/collab/CURRENT-SUPERVISION.md` 等），
  未触碰。

## 沿用 r2 的 4 项待裁偏差（本轮未改）

1. 零命中时 hits CSV 不存在 vs 合同“存在且 0 行”（`OutputManager` 惰性打开）。
2. Stage B 负例在受支持输入下不可构造（声明与内核几何同源）；正例每次启用运行都执行。
3. Case M 线程调度不确定：只作可重复性诊断，不作 fail 判据（属于 H3-4）。
4. 无法证明材料对应时必须 `unknown`，不得伪造 `true`。

## 复现

```bash
python -B scripts/test_parallel_world.py
build_vs2026/Release/G4UniversalSim.exe --config main.ini --macro switch.mac --output out/lc   # 在 out/collab/20261107-h3-lifecycle-overlap-r3/repro/lifecycle-geometry-switch 下
build_vs2026/Release/G4UniversalSim.exe --config main.ini --dry-run   # 在 .../repro/overlap-precision-repro 下，应为非零并以 overlap in their interior 拒绝
```

本轮范围到此为止，停写等待独立复审；不自行启动 H3-3/H3-4。
