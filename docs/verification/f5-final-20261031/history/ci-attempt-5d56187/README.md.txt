# F5 5d56187 CI 最终取证：收集完整，严格基线未通过

记录日期：2026-10-31（本地）。原始报告/API/日志的时间与内容均保留。

**CI官方全成功；约定的独立验收仍失败。** 唯一拒绝是 Linux Geant4 11.4.3 的 backend F4同代基线：39,795 < 39,797，具体 `displacement_damage` 为44 < 46。不得以官方绿灯覆盖本门禁，也不得将本报告称为F5阶段关闭。

候选唯一提交：`5d56187392a2e7b888d5ce13f8da05a295cba6d4`。

- [Linux run41082364530](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41082364530)：Geant4 11.3.2 / 11.4.3 两个job全部success。
- [M0 run41082364655](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41082364655)：Windows / Ubuntu 两个job全部success。

| 平台 | Profile用例数 | 用例总数 | v3入口总数 | 严格F4基线 |
|---|---|---:|---:|---|
| Linux Geant4 11.3.2 | static32 / GUI47 / backend59 / integration22 | 160 | 50837 | 4/4通过 |
| Linux Geant4 11.4.3 | static32 / GUI47 / backend59 / integration22 | 160 | 50245 | 3/4通过，backend失败 |
| M0 Ubuntu | static32 / GUI47 | 79 | 5964 | 2/2通过 |
| M0 Windows | static32 / GUI47 | 79 | 5957 | 2/2通过 |

## 原始字节、身份及证据完整性

- 两workflow、四job、四官方ZIP、**十二报告、478次case执行**全部实际收齐，没有fail/skip case或零断言用例。
- 四ZIP SHA256与GitHub官方artifact digest、字节长度一致；**492个ZIP文件成员**逐字节与解包文件核对，并检查绝对/逃逸/重复/符号链接路径。官方digest与本地SHA详见 `evidence-integrity-audit.json` 的artifacts。
- 478份case日志原始字节SHA与报告一致，实际v3 marker与报告断言数一致；报告总数、逐case名单/顺序与冻结manifest一致。
- 十二报告与artifact/run/job均绑定唯一5d56187；源码指纹 `db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc`，测试指纹 `b2de2edaca1e30c1bacc10cefad277549a138a49d06f2daa784166e9385da2ce`，全部匹配。未借用任何旧SHA报告，也没有F4双提交例外。
- Linux两个job官方负向对照均拒绝篡改日志digest；其job日志中的 `/tampered/ report evidence: FAIL` 是预期反例，与正式报告通过区分。
- 四份实际Qt版本/引用寿命收据通过；两Linux的三项原生helper构建及六次运行收据通过；backend/integration报告的实际版本、Release、多线程、GNU及来源验证符合冻结条件。
- Linux八份报告 `git_dirty=true`，M0四份 `false`，**原值保持**。没有原始runner porcelain，不猜测dirty来源、不声称Linux runner clean；源码/测试指纹与tracked-source inventory是另外核对的事实。

## 唯一严格门禁失败

收据：`baseline-gates/linux-evidence-11.4.3-backend.log`；全部12份基线中11份通过。当前与F4的59个backend case，仅 `displacement_damage` 计数改变，46→44；另外58个计数相同。

只读比对确认 `scripts/test_displacement_damage.py` 和 `tools/test_assert_probe.py` 在F4实际CI提交a9ad09d与5d56187之间无diff；两个DDD日志除最后assert marker外字节完全一致。脚本153–156每条worker summary行执行一次assert，可能受实际MT事件分配影响；目前没有旧/新原始worker CSV或逐断言轨迹证明原因，**没有据此豁免、改旧报告或放宽阈值**。该问题是确定的证据门禁拒绝，尚不能等同为DDD物理结果回归。

主审须先处置此项，再决定是否可关闭F5。本分工未修改产品、正式测试、workflow或任何历史报告，未重启CI。

## 入口与可复核资料

- `evidence-integrity-audit.json`：完整机器收据，`status=failed`、`evidence_collection_complete=true`、12report/478case、仅一个problem。
- `evidence-integrity-audit.log`：审计进程exit1原始输出。
- `audit-ci.py`：独立审计脚本。`frozen-case-manifest.json`为root原冻结清单，未改。
- `*-run.json`、`*-jobs-api.json`、`*-artifacts-api.json`：官方API元数据；`job-*.log`为connector解码UTF-8完整job日志，不声称是GitHub日志ZIP的原始传输字节。
- 四 `.zip` 与四同名解包目录：官方原件与成员；`baseline-gates/`保留12份严格门禁结果。
- `partial-m0-audit.*`、`linux-1143-ready-gates.log`与`README-pending.md`是中途检查点，原样保留；本README及完整JSON定义最终收集结论。
- 归档建议见 `archive-file-manifest.json`。未保存签名临时下载URL或API密钥；下载链接仅经关闭echo的本地stdin传递。建议将本轮放在最终归档下的 `ci-attempt-5d56187`，如后续换候选，不得覆盖或改成成功证据。

本CI审查不代替root的Windows全量、原生窗口观察和正常退出，不推断科研物理验证。
