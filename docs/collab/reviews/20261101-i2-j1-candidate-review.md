# I2/J1 候选审查汇总（2026-11-01）

**结论：这是实施候选审查记录，不是 I2/J1 阶段关闭批准。** 已闭合的窄问题不能覆盖未完成的完整矩阵、实际 GitHub Actions、新主机交付与原生窗口验收。当前审查基于计划提交 `b1c8f9c` 上的未提交实现叠加，不把该提交称为产品冻结身份；最终源码、二进制和证据身份须由主负责人另行固定。

本文汇总现有审查与实测，不重写旧失败为成功。必要原始审查与小证据已持久归档于[证据目录](20261101-i2-j1-evidence/README.md)：原始字节保存在 ZIP，原件/阅读副本各有 SHA-256 清单。`out/collab/` 仅表示当时本机来源，干净检出不要求存在该目录；完整阶段证据与身份映射仍须另行闭合。本文作者参与过 3D 外观及 MT/GDML 测试修复；这些项目的实现者自测单独标注，不冒充独立审查。

## 已闭合的窄问题

| 问题 | 当前结论 | 依据与边界 |
| --- | --- | --- |
| J1 首次显示 3D 未自动预览 | P2 独立复审关闭 | 用户配置导航、显示按钮和菜单启用走已有计时器；首次导出 1 次、旧标签随后累计 2 次。纯布局预设/恢复/浮动不排队。自动分支读取 Project、材料和几何副本，手动语义保持；原始非法草稿、F5 revision、K1 levels/records 不变。见[修复复审](20261101-i2-j1-evidence/reports/01-j1-preview-p2-final-independent-review.md)、`j1-preview-p2-independent-fixed.log`、`j1-preview-p2-independent-readonly.log`。不等于完整原生运行中验收。 |
| J1 布局单实例及 F5/F4 适配 | 限定范围通过 | 配置、3D、结果和日志保持原实例，九页逻辑身份保持；显示操作不生成项目编辑或运行控制。真实键入紧邻浮动前后仍捕获，Undo/Redo 保留非法原文；隐藏字段与显式 dock 的诊断可达性分开。见[布局独审](20261101-i2-j1-evidence/reports/02-j1-layout-independent-review.md)、`j1-layout-review-workspace.log`、`j1-layout-review-f4.log`。其中首次预览 P2 以后续复审关闭，不用原专项绿色覆盖该遗漏。 |
| 安装窗口重开不能恢复/清理 | P2 窄复审通过 | 合法 journal 恢复同计划身份；旧 journal 无计划仅清理。界面不自行安装或选择环境。见[安装 UI 复核](20261101-i2-j1-evidence/reports/03-i2-install-ui-fix-review.md)、`i2-install-ui-fix-review-evidence.json`。 |
| 安装发布与正在检测并发，自动候选丢失 | P2 独立复审关闭 | 保留 `candidates=None` 自动发现，新增候选独立追加并去重，忙时排队 fresh 检测；实际旧/新候选共同保留，关闭后迟到发布不新启检测。见[最终 UI 复审](20261101-i2-j1-evidence/reports/04-i2-install-ui-final-review.md)、`i2-install-ui-final-review-evidence.json`。 |
| 冻结复用绕过来源检查、默认复用源被清理 | 两项 P2 已由另一窄独审关闭 | 冻结封条绑定实际源码和完整产物字节，缺收据/旧源码/篡改拒绝；任何清理前校验复用源与目标，标准旧 `work/dist` 可保留复用，复制后再次验证。见[冻结复用独审](20261101-i2-j1-evidence/reports/05-i2-freeze-identity-independent-review.md)、`i2-freeze-identity-independent-test.log`。不是发布签名或来源真实性证明。 |
| `out` 根或中间 junction 可逃逸清理范围 | P2 已由同一窄独审关闭 | resolve 前检查 symlink/reparse，合法根必须恰为检出的 `out`；两个 Windows junction 反例中删除调用均为 0、源字节不变，普通临时目录真实清理仍通过。Windows/POSIX 单例分别 33/31 个探针入口，见 `i2-freeze-identity-path-review-fixed-evidence.json`、`i2-freeze-cleanup-alias-regression.log`、`i2-freeze-cleanup-alias-posix.log`。未清理实际发布产物。 |

上述未写目录前缀的日志和 JSON 按[归档清单](20261101-i2-j1-evidence/manifest.json)的原 source 路径查找阅读副本或 ZIP 条目。旧 UI/快照/联接/预览失败均保留原语境；未入选的探索材料不冒称已持久归档。

## 必须保留的关闭生命周期纠正

最初将默认恢复根提前解析为 Path 的方案已经撤回。它会改变 `_setup_experiment` 的 `records_root` 分支：原默认 `None` 使用项目 runsRoot，提前显式 Path 则切到恢复目录下的空历史范围。此前“无语义变化”“初始化顺序修复”的审查判断均已明确撤回，不能继续引用其绿色结果归因于 QStandardPaths。

当前修复遵守产品异步关闭：历史 EvidenceJob 尚未排空时 `close()` 可以拒绝；自检超时保持窗口有效，服务正常关闭后才 DeferredDelete。默认 `None` 与环境变量覆盖的真实 history gate 分别测试了拒绝后保留、释放后销毁及正常退出；源码自检保留九页、图表、可选 3D 和中文覆盖。见[带撤回历史的生命周期独审](20261101-i2-j1-evidence/reports/06-j1-recovery-order-review.md)、`j1-default-entry-deferred-close-wait.log`、`j1-review-current-default-none.log`、`j1-review-current-override.log`、`j1-review-current-selftest.json`。

QtCore 冻结 DLL 污染是另一个故障层：子环境 PATH/Qt/Python 路径清理和来源审计已经窄独审；不能与忽略关闭拒绝后的销毁混作同一根因。见[冻结启动审查](20261101-i2-j1-evidence/reports/07-windows-freeze-fix-review.md)。

## MT 派发与 GDML 能力范围

### MT 小事件测试假设修复

Windows 11.4 开发矩阵原失败日志及散列保留在 `out/collab/run-summary-mt-review/original-run-summary-failure.log`、`original-failure-identity.json`；原临时输出已删除，不能补造其逐 worker 事实。独立实际复现的 `baseline/native-2` 首轮 8 事件全由 worker0 完成，worker1 没有该轮 hits，后两轮双方参与；严格观察器核对全部 24 事件的粒子、能量、三轴起点及 event_edep 归属无误。

修复后仍为每轮 8 事件、2 worker，每个 attempt 完整核验逐轮/总事件、实际文件与 primary。仅语义正确但 worker 覆盖不足才独立重试，最多 6 次；必须同一次 attempt 的每个 run 都实际观测到两个 worker，任何语义错误立即失败，耗尽仍失败。每次实际输入、输出、日志及 worker-event 分配永久保存。没有以增加事件数、删除“两 worker”目标或累加不同 attempt 的片段替代证据。

该修复由本文作者实施；候选完整 `run_summary` 开发测试退出 0、28,715 次断言，最后源码的实际窄 helper 另绑定脚本/EXE SHA 并通过。负例覆盖错误能量/位置、缺失/重复/错归属、覆盖耗尽及语义错误不重试。见[实施与证据边界](20261101-i2-j1-evidence/reports/08-run-summary-mt-review.md)、`run-summary-mt-review/current-helper/identity.json`。最终正式矩阵仍须使用最终测试指纹执行，不把实现者自测当作独立验收。

### GDML-off 只验证明确拒绝

实际能力查询决定分支；未知/缺失/类型错误不得降级为 OFF。ON 原 GDML 轮回、身份、共享场、事件数及物理容差保持原样，仍须在实际支持的 Windows 11.3、Linux 11.3/11.4 组合执行。Windows 官方 11.4 SDK 的 OFF 分支不能称 GDML 功能已验证，也不能与 ON 基线断言数量直接等同。

本文作者按授权补充了三项测试的 OFF 分支及共享 helper：偏置 24 夹具、可触体 10 夹具、共享场 1/2 线程分别实际早拒绝，不产生模拟 CSV/ROOT 等；无摘要时明确记录早期拒绝，有摘要则必须 failed、零 run/事件。完整 A7 其余解析与场运动判据继续执行。当前 OFF 探针入口为 bias 49、touchable 11、A7 252，均退出 0；这是实现者测试记录，不是 ON 物理或身份验证结论。

旧三项失败日志复制并 SHA 登记于 `out/collab/gdml-off-candidate/original-failure-identities.json`；实际夹具、日志和 helper 反例见[实施记录](20261101-i2-j1-evidence/reports/09-gdml-off-test-implementation.md)。主负责人 `test_geometry_a5.py` 的 GDML-off 三个真实拒绝例经只读审查，ON 原路径保留；其运行证据保持主负责人原身份。

## CI 窄问题修复复核，实际运行仍待完成

以下两项已经修复并通过独立小夹具复核；这不是实际 GitHub Actions run 或 freshhost 验收。原失败记录保留在[CI 独审](20261101-i2-j1-evidence/reports/10-i2-ci-delivery-independent-review.md)，文末追加闭合结论，没有覆盖原文。

| 级别与状态 | 原问题 | 修复与独立证据 |
| --- | --- | --- |
| P1，已关闭 | 快照共同漏掉产品 `gui/g4usim_gui/output/` | 改为 repo-relative 生成目录排除，保留产品 output 包及额外模块、新 packaging 工具；清单校验加必需产品路径。小夹具完整复制并核对 hash，缺必需模块实际拒绝。原漏件反例仍保留。 |
| P2，已关闭 | SDK build 日志未上传，冻结日志/审计在归档前清理 | 归档函数收集本轮真实 freeze/SDK 诊断及封条，写 size/SHA/source-stability 索引；stage finally、顶层 finally 和中间目录清理前均接入，已有 workflow 的 evidence 上传路径覆盖它。小夹具 9 文件复制/hash通过，重复不增记录，变化日志另存新版本，删除本次中间 out 后 10 条归档均存在。 |

复核脚本与原文证据在 `out/collab/i2-ci-review/review_ci_fixes.py`、`ci-fixes-small-review-evidence.json`、`ci-fixes-small-review.log`；原虚拟环境独立退出 0。第一版探针的 Windows 字符串路径选择错误独立保留，不计为产品失败。没有下载、冻结或运行完整 flow。

末版协调器记录阶段磁盘观测、预算与 owned 中间副本清理，完整应用源码 SDK 构建默认启用；中间版本的“无预算”和可选 flag 失配不再列为当前缺陷。数据获取脚本明确 MD5 是 SDK 遗留完整性检查、观察 SHA-256 不是发布签名；真实 SDK 配置解析及 8 种恶意 tar 小夹具拒绝已检查，未下载数据。独立 desktop job 的另一次 freeze 仍不能代替 full-installation job 的实际成功收据。

## 首轮 CI 与本机报告的新增边界

`ba81615` 的 Linux M0 run `41306094888` / job `124846661583` 暴露了本候选文档 10 个本机 out 链接；本次归档修订对此补证，不把原失败改成通过。Windows 同轮失败发生在 checkout 长路径阶段。另一本机 static 报告为 42 pass / 1 fail（platform_paths），其中历史路径 D 来自未启用 longpaths 的子进程观测，与启用 core.longpaths 后的 clean 状态区分，原报告保持。当前 GUI 为 57/59，仍有失败；这些不是最终身份或阶段通过证据。

## 阶段关闭仍需的证据

- 最终源码和测试身份固定后的完整 Windows/Linux、版本与能力矩阵及严格报告门禁；开发单例、失败后窄重跑不能代替。
- 实际 GitHub Actions run 的提交、runner、scope、状态和可下载证据；workflow 文本、源码审查或本机同拓扑不等价。
- 最终冻结包及 runtime/SDK、干净主机上的实际安装/恢复/运行/编译/卸载链路；文件安装、I1 环境就绪、K1 模拟完成、指定参考下的物理验证继续分别判断。
- J1 原生窗口的实际拖拽、缩放、隐藏、浮动、重启恢复/复位、运行中操作、代表性 DPI、中英文与退出；离屏区域矩形、组件渲染截图不能单独批准。

本汇总不改 STATUS/ROADMAP，不缩减原验收范围，不批准发布或宣布 I2/J1 已完成。主负责人完成剩余证据与 CI 待复核项后，再作阶段判断。
