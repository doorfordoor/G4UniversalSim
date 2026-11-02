# L1 docs-only 集成收据 B（2026-11-02）

本页持久记录已完成的 A 集成时点；后续分支推进不回写这一历史快照。本次 B 只新增本收据，不修改封存目录，也不改产品、测试、workflow、属性或原验收结论。

## A 提交与远端

- 测试／构建冻结：`246e4f6f1b97cc5e0651ff01262c85cf2e9c28d3`。
- 文档／证据提交 A：[`ebb4098372a01cff55af17283921bf2e16eec167`](https://github.com/doorfordoor/G4UniversalSim/commit/ebb4098372a01cff55af17283921bf2e16eec167)，父提交为上述246冻结。精确变化仅九份文档与32份公共归档文件；其它tracked路径的类型、模式与内容保持。
- A 正常推送后，`origin/roadmap/L1-config-agent` 与 `origin/codex` 实际远端引用均核为 A。codex由原`4840e62e6c2efe935e74e5b934f6194c6aa7731c`在其原worktree正常fast-forward，没有force push。
- 原EXE／report仍保留246或各自EE历史身份，不为文档提交伪改BuildInfo，不声称A重跑了模拟。

## 三工作树复核与D盘保留

| 工作树 | A集成后实际HEAD | 核查 |
|---|---|---|
| effective-config，roadmap/L1-config-agent | `ebb4098372a01cff55af17283921bf2e16eec167` | tracked clean；公开32文件Git blob与原封条字节匹配 |
| q1-final，codex | `ebb4098372a01cff55af17283921bf2e16eec167` | tracked clean；18份报告／匹配基线重放通过 |
| D盘，roadmap/gui-theme-response | `42865de954025cf53549b196bce26bd840510a02` | tracked clean；保留独立字体／主题源码与测试；原1153个untracked名称、大小及SHA逐项不变 |

D盘合并父提交为原`dd312aed749ca970b85cf3706b195d25430e4ba0`与A。STATUS及gui/AGENTS两处相邻插入冲突保留双方说明；15条非重叠D改动路径原字节保持，三个重叠人类文档中的D说明也核保留。D产品与正式246产品有已存的字体／主题差异，不冒充整份D源码通过246正式矩阵。此轮仅正常推送L1与codex两个正式引用，D分支本机同步，没有额外推送第三分支。

## 归档与严格重放

[正式证据](../../verification/l1-final-20261102/README.md)共32个公共文件／3420021字节；两个ZIP保存1285个精选原件。18份原报告、970份原日志在C、codex与D均以冻结checker及稳定公开J2匹配基线重放通过，无原OUT绝对日志路径回退；篡改摘要负例被拒。原报告／日志字节与状态不改，旧失败不拼成新成功。

- C链接检查：261份文档、1006个相对链接、0缺链；D：263份、1010链接、0缺链，均为A集成时点的原计数。
- 公开原图／原UIA载荷0；新Windows122项和Linux16项仅五字段元数据，原件永久local-only。
- 封存公共清单[public-files.manifest.json](../../verification/l1-final-20261102/public-files.manifest.json)的SHA256为`70077ce328fbe78415fc8206b9bc1b3a60b130edff7b6f5c6e0aa7b1b38176a2`；B不修改该目录或封条。
- 仅文档／归档验证，未因纯docs提交重复GUI／模拟。原件CRLF按已有`-text`保存，不能为消除空白提示改原字节；未新增属性豁免或放宽报告门禁。

## 必须保留的签收限制

Linux代表性原生通过的是独立真实X11/xcb桌面的可见／操作及清理：1 request／1 task／0 events，plan步骤passed，但整任务随后在300秒预算处**FAILED／agent.task_timeout**。显示辅助退出码`[0,1,0]`、两组owned为空及HTTP关闭照实保留；WSLg RAIL未成功，不能被新通道改绿。确定性协议夹具不代表本地模型语义质量或物理正确。

EE云任务、人工单对、单点恢复与production closed-load仍按原HEAD／EXE和有限范围引用；不推导人口成功率、提速或通用NL可靠性。F2、K2、L2及独立科学验证仍按原路线图推进。

B的真实提交、后续D合并及远端复核由实际Git元数据和同步进度记录表达，不在本页自填未来SHA。后续文档提交不改变本页记录的A历史时点。
