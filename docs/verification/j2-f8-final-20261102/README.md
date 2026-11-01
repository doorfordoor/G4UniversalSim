# J2/F8 最终证据：2ec5b14 功能验收冻结

main已接受本轮J2/F8及E7限定范围的功能验收依据。**正式构建与测试冻结为 `2ec5b14fc823ad837dce3ea6f5d7c5ae3f66a3c8`**；包含本文件的后续提交仅为docs/evidence，不改变原report或EXE身份，不因此重建或重跑完整矩阵。其交付身份由实际Git树、三份精确锁及main后置byte-map确认，不在本文自填未来commit SHA造成自引用。

六份Windows正式报告 **300/300、181357入口**，六launch均runner/gate0、identity_errors=[]，report均git_dirty=false。真实CI四workflow／八job均原attempt1 success，**12份报告636次case执行、221186实际assert入口、12 strict pass、零skip**；这些是跨平台/profile重复执行数，不是唯一测试定义。Desktop／Install交付收据单列，不伪加到636。Windows aggregate原SHA `a701f34fc2d3e9bd2d0aec9fc833d249179fc76ad5de873f8c42011e665ec73c`。

E7只完成本轮既有15原语／7布尔工具的统一factory注册、能力元数据和GUI离线定义接线；兼容、缓存／生命周期及适用矩阵通过。实体集合、A5实验性等级、assembly拒绝、GDML版本限制及科学支持等级不变，不宣称完整GeometryConfig校验器重写、任意worker构造或新的输运物理基准。

## 可读入口与原件

- [允许文件、原SHA及恢复路径](manifest.json)
- [197张local-only图及opaque排除元数据](metadata-only.json)
- [原身份和main限定范围索引](scope-index.json)
- [原字节与本目录report-log闭合核验](verification.json)
- [当前6＋12实际门禁计划](current-gates.plan.json)
- [独立搬移目录执行的当前严格门禁收据](current-gates.receipt.json)
- [现有根属性与Git blob原字节证明](git-blob-proof.json)
- [全部实际公共文件精确清单](public-files.manifest.json)
- [只读公共核验工具](tools/verify_public.py)
- [原checker门禁执行工具](tools/check_current_gates.py)
- [独立OUT目录历史布局恢复工具](tools/restore_archival.py)

## 当前正式报告与matching历史

| 报告 | case执行 | 实际assert入口 | 原报告／严格matching基线 |
|---|---:|---:|---|
| Windows-windows-static | 46 | 4586 | [report](tree/out/verification/j2-f8-2ec5b14/windows-static/20261102-052959-87f97644/report.json) / [matching baseline](tree/out/verification/i2-j1-5fe0a10/windows-static/20261101-205231-c62d61cd/report.json) |
| Windows-windows-gui | 66 | 8636 | [report](tree/out/verification/j2-f8-2ec5b14/windows-gui/20261102-053011-53d49584/report.json) / [matching baseline](tree/out/verification/i2-j1-5fe0a10/windows-gui/20261101-205241-d4aff2d8/report.json) |
| Windows-windows113-backend | 63 | 82029 | [report](tree/out/verification/j2-f8-2ec5b14/windows113-backend/20261102-053015-033f0a7f/report.json) / [matching baseline](tree/out/verification/i2-j1-5fe0a10/windows113-backend/20261101-205411-0e9901a5/report.json) |
| Windows-windows114-backend | 63 | 72536 | [report](tree/out/verification/j2-f8-2ec5b14/windows114-backend/20261102-053010-077a8457/report.json) / [matching baseline](tree/out/verification/i2-j1-5fe0a10/windows114-backend/20261101-205411-79e165c8/report.json) |
| Windows-windows113-integration | 31 | 6790 | [report](tree/out/verification/j2-f8-2ec5b14/windows113-integration/20261102-060158-291be458/report.json) / [matching baseline](tree/out/verification/i2-j1-5fe0a10/windows113-integration/20261101-213823-a10c064e/report.json) |
| Windows-windows114-integration | 31 | 6780 | [report](tree/out/verification/j2-f8-2ec5b14/windows114-integration/20261102-061507-7d5768e9/report.json) / [matching baseline](tree/out/verification/i2-j1-03d2c48/windows114-integration/20261101-221315-6389b5dd/report.json) |
| CI-linux-evidence-11.4.3-backend | 63 | 72874 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/linux-evidence-11.4.3-13103140474/linux-backend/20261101-214039-f4277fb7/report.json) / [matching baseline](tree/out/verification/i2-j1-03d2c48/ci/extracted/linux-evidence-11.4.3-13087926895/linux-backend/20261101-142038-73ddc795/report.json) |
| CI-linux-evidence-11.4.3-gui | 66 | 8615 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/linux-evidence-11.4.3-13103140474/linux-gui/20261101-213253-d431370f/report.json) / [matching baseline](tree/out/verification/i2-j1-03d2c48/ci/extracted/linux-evidence-11.4.3-13087926895/linux-gui/20261101-141602-5d59f966/report.json) |
| CI-linux-evidence-11.4.3-integration | 31 | 6770 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/linux-evidence-11.4.3-13103140474/linux-integration/20261101-215424-8887e69e/report.json) / [matching baseline](tree/out/verification/i2-j1-03d2c48/ci/extracted/linux-evidence-11.4.3-13087926895/linux-integration/20261101-143513-c440e9a9/report.json) |
| CI-linux-evidence-11.4.3-static | 46 | 4573 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/linux-evidence-11.4.3-13103140474/linux-static/20261101-213131-5e8b77d1/report.json) / [matching baseline](tree/out/verification/i2-j1-03d2c48/ci/extracted/linux-evidence-11.4.3-13087926895/linux-static/20261101-141435-fe86f483/report.json) |
| CI-linux-evidence-11.3.2-backend | 63 | 82020 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/linux-evidence-11.3.2-13102513206/linux-backend/20261101-214208-e7433889/report.json) / [matching baseline](tree/out/verification/i2-j1-03d2c48/ci/extracted/linux-evidence-11.3.2-13087921872/linux-backend/20261101-142031-b85b3b32/report.json) |
| CI-linux-evidence-11.3.2-gui | 66 | 8615 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/linux-evidence-11.3.2-13102513206/linux-gui/20261101-213257-6a7d8451/report.json) / [matching baseline](tree/out/verification/i2-j1-03d2c48/ci/extracted/linux-evidence-11.3.2-13087921872/linux-gui/20261101-141600-27d9f9ea/report.json) |
| CI-linux-evidence-11.3.2-integration | 31 | 6770 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/linux-evidence-11.3.2-13102513206/linux-integration/20261101-215736-ac86f816/report.json) / [matching baseline](tree/out/verification/i2-j1-03d2c48/ci/extracted/linux-evidence-11.3.2-13087921872/linux-integration/20261101-143523-ce41a587/report.json) |
| CI-linux-evidence-11.3.2-static | 46 | 4573 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/linux-evidence-11.3.2-13102513206/linux-static/20261101-213122-6488715c/report.json) / [matching baseline](tree/out/verification/i2-j1-03d2c48/ci/extracted/linux-evidence-11.3.2-13087921872/linux-static/20261101-141435-473d56e4/report.json) |
| CI-m0-report-windows-latest-static | 46 | 4573 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/m0-report-windows-latest-13102896151/20261101-212954-d3f500ec/report.json) / [matching baseline](tree/out/verification/i2-j1-6310969/ci/extracted/m0-report-windows-latest-13088128041/20261101-144208-6260dda6/report.json) |
| CI-m0-report-windows-latest-gui | 66 | 8615 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/m0-report-windows-latest-13102896151/20261101-213444-b4dae0f9/report.json) / [matching baseline](tree/out/verification/i2-j1-6310969/ci/extracted/m0-report-windows-latest-13088128041/20261101-144550-80bc5c13/report.json) |
| CI-m0-report-ubuntu-latest-static | 46 | 4573 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/m0-report-ubuntu-latest-13102097206/20261101-212938-f67e746d/report.json) / [matching baseline](tree/out/verification/i2-j1-6310969/ci/extracted/m0-report-ubuntu-latest-13087119373/20261101-144135-4d7ff67f/report.json) |
| CI-m0-report-ubuntu-latest-gui | 66 | 8615 | [report](tree/out/verification/j2-f8-2ec5b14/ci/extracted/m0-report-ubuntu-latest-13102097206/20261101-213124-da0a127d/report.json) / [matching baseline](tree/out/verification/i2-j1-6310969/ci/extracted/m0-report-ubuntu-latest-13087119373/20261101-144310-866ffdc4/report.json) |

门禁命令由上表明确路径生成，原checker无改动，无allow-incomplete／legacy放宽。标准执行形式：

```powershell
python -B tools/check_current_gates.py --output ../new-unique-gate-receipt
# 工具逐项执行：
python -B tree/scripts/check_report_evidence.py --report <report路径> --baseline <上表matching-baseline路径>
```

本轮18份当前门禁均预期exit0；另选一份旧失败作预期exit1反向控制。全部旧17份失败的原命令／exit1收据及原SHA保留在恢复映射中，[旧fail预期清单](historical-failure-gates.json)不是新绿色证据。原56b/2901/18c失败不修改或拼成2ec结果。公共目录已经另置独立路径核验，所有报告日志必须由本目录实际原件解析；若落回任何旧绝对路径即失败。

CI 工作区状态按原件分别记录：六份Windows和四份M0报告为clean；Linux双版本八份报告原git_dirty=true，状态仅对应版本的`.g4env-11.3.2/`或`.g4env-11.4.3/`、`.micromamba/`、`bin/`三行未跟踪环境目录。其tracked_source_gate=pass、untracked_source_files=[]，source/tests/merge均匹配2ec；不泛放其它dirty，也不把原JSON改成clean。[独立状态解释收据](tree/out/verification/j2-f8-2ec5b14/ci/review-git-dirty-supplement.json)另存。首次归档附加blanket-notdirty检查首败及原stderr保留，与产品或原CI失败分开。

## 原生范围与身份

18c三档原生仅按149GUI/C++与精确7文件允许差异的实际byte-map映射，仍用原HEAD／EXE／scope，不能冒充新构建全三档重跑。新2ec仅125%代表性补验：main实际I1发现/I2首屏打开关闭、Import原18c离线包并保存、模板Finish与另存、重入Next/Back/Esc后正常退出；24观察、41原JPEG，原6497/launch/exit均0、CIM remaining0。Ptolemy只做纯文件独审，不是第二次视觉复验。Harvey合同余项核对认为无需新增原生动作，不替代正式门禁。

Import保留4条stale历史，唯一当前passed是import_history（imported_count4）；本轮validate/generate/run新record为0，不能写成本地验证绿。两个项目实际独立保存，模板Finish字段已应用；自动两体积Geant4预览可能调用构造后端，既不是事件Run，也不能称完全未启后端。缓存project/Undo/focus不是live F5快照。旧100%初始化no_run、run100/100与导出replay_verified=false分别保留；未新增CLI replay、物理跨屏/热插拔或科学基准。

## 公共payload和历史文本边界

197张标记local-only图（70继承QQ、86旧18c、41新2ec）只公开path/size/SHA及观察边界，原图仅本机；objects和tree都实际排除，不能机械搬整个私有staging。small opaque ZIP未作内容归属扫描，一律metadata-only，不凭ZIP SHA判安全；其它允许任务图沿原选择，不因QQ一刀切排除。本投影准备／核验未执行公开上传，最终Git发布由main负责。

原历史Markdown含失效旧链接或指排除图时，仍按原字节存为`.md.raw`与内容寻址对象，并提供恢复映射，不把它们作为有效公共Markdown导航。当前可读README只链接实际允许存在的目标；全局check_doc_links规则不改。恢复工具仅在新独立OUT／兄弟目录恢复档案，拒绝覆盖；恢复的旧md不是要提交的公共入口。

原report/log字节、状态、HEAD和失败保留；无原绝对日志fallback。现有根`docs/verification/** -text`适用于公共目标，原CRLF/LF按Git blob实测保字节，未新增attrs／修改全局配置。公开范围限于本清单允许的任务证据；被排除的本机图片、二进制和未审查压缩包只保留元数据，文件哈希不替代内容审查。main最后负责精确apply、全部product/tests字节身份、实际Git树三锁后置映射与正常ff/push；这些不是新的运行／物理证明，也不触发新formal循环。
