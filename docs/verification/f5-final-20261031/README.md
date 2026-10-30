# F5 配置事务、撤销与恢复：最终验收

**F5 已在约定范围完成实现、审查与验收。** 正式自动矩阵、原生身份映射和最终独立归档审查全部通过；分支集成在实际完成后另行登记。

冻结验收提交：`5c1eec5007cd29cbe12949c19bed81457f1f825b`。产品实现来自 `5d56187392a2e7b888d5ce13f8da05a295cba6d4`；其后仅修正测试证据判据、增加原始证据和更新实施提案。Windows 与全部正式 CI 使用新冻结提交。原生交互仍归属 5d，未改写原收据，详见[身份映射](identity/identity-map.json)及[独立复核](identity/identity-map-independent.md.txt)。本阶段没有新增科研物理能力。

## 已交付范围

- 主 Project/Configuration 的材料、几何、源、物理、计分和运行参数共用事务、Undo/Redo 与保存点；成功应用向导为一个事务。项目 v7 保留完整编辑状态和非法原始草稿，已知 v1–v6 继续兼容；非法输入仍阻止生成。
- 自动保存使用独立恢复副本、原子发布和系统会话锁；未命名项目也可恢复。恢复打开未命名、未保存副本，原项目和外部源文件不被覆写；损坏或不支持的恢复文件保留并说明。
- 从捕获的源文本重建来源约束；撤销/恢复使旧诊断、Inspect、预览、包绑定及运行成功状态失效。投影和回滚双失败时冻结有风险入口，保留最后确认快照并提供修复；容量/预检拒绝不得改变旧状态。
- 默认 100 个操作、32 MiB 是历史快照编码预算，不是应用总内存上限。独立扫描/场景和未应用向导草稿不进入主历史；Undo 不撤销磁盘输出或已运行的进程。新取扫描基础仍检查主编辑器状态。

使用说明：[配置撤销与恢复](../../配置撤销与恢复.md)。范围与修正决定：[实施约定](../../collab/inbox/20261030-2155-astra-f5-execution.md)。

## 正式自动矩阵

| 平台 | 通过用例 | v3入口 | 原F4严格门禁 |
| --- | ---: | ---: | --- |
| Windows Geant4 11.3.2，完整矩阵 | 160/160 | 50898 | 通过，旧152项/49913逐例及总量 |
| Linux Geant4 11.3.2 | 160/160 | 50866 | 四profile均通过 |
| Linux Geant4 11.4.3 | 160/160 | 50274 | 四profile均通过 |
| M0 Windows，无Geant4 static/GUI | 79/79 | 5957 | 两profile均通过 |
| M0 Ubuntu，无Geant4 static/GUI | 79/79 | 5964 | 两profile均通过 |

全部正式报告要求无 fail/skip/零断言用例；原 F4 同平台、同 Geant4 版本和同 profile 的逐例与总量门禁均保留。实际 v3 入口次数不是独立科学命题数，不等同物理正确性。

- [Windows 原始报告](windows/final-1/report.json)、[F4 Windows 原始基线副本](baseline/f4-windows/report.json)。
- [CI 官方身份与概要](ci/ci-evidence.json)、[完整独立审计](ci/evidence-integrity-audit.json)。四份官方 ZIP 的摘要、成员与解包日志均复核；12 份报告、478 次 case 执行按冻结清单核对。
- Windows 可执行文件与构建配置见 [构建收据](ci/windows-build/receipt.json)。Linux `git_dirty` 保留原值及真实 `git_status_porcelain`，仅按实际路径解释，不把源码指纹一致冒充整个目录干净。

官方运行：[Linux 41090605959](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41090605959)、[M0 41090605955](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41090605955)，均绑定5c1eec5。Linux的原样Git状态仅列未跟踪的 `.g4env-<version>/`、`.micromamba/` 和 `bin/`；workflow分别指定环境前缀/根前缀并解包 `bin/micromamba`。没有跟踪源码变更，源码与测试指纹另经核对；M0两平台状态为空。

## DDD 测试证据修正

5d 的官方 CI 全部成功，但严格门禁拒绝 Linux 11.4.3/backend：DDD 的实际入口次数 44 小于旧基线 46。脚本和探针未变，差异来自稀疏 summary 行循环；原 CSV 已清理，不能反推当时哪个 worker 少了哪些记录。该次[失败审计](history/ci-attempt-5d56187/evidence-integrity-audit.json)保留，未改成通过。

新测试保留原全部物理判据、体积条件和容差；按固定不变量检查全部行，并加入合法稀疏分配及损坏反例，成功计数为 73。首轮输入、CSV、metadata 和摘要原字节另存，便于直接复核。开发 r2 曾强制可见 worker N 等于 master N，经独立审查撤回：现在只要求可见 worker 去重 N 不超过 master N，空表头的事件数未知。原始结果不能被扩张为完整重放包或每事件轨迹验证。

[r3 修正说明](review/f5-ddd-stable-r3-handoff.md.txt)、[修后独立复核](review/f5-ddd-independent-recheck-r3.md.txt)。

## Windows 实窗与证据边界

在产品 5d 上完成 22 份观察、28 张截图和实际关闭退出 0，129 个 GUI 文件与新候选的原字节/Git blob 一致；新后端源码指纹、构建方式、编译器及 Geant4 版本也核对一致。没有声称新提交再次进行实窗交互，亦没有声称两个可执行文件字节相同。

观察覆盖非法草稿、Undo/Redo、保存和关闭取消、自动保存状态、原件已变化时的恢复副本、损坏恢复项、投影双失败后的冻结/修复、主题及语言切换。[直接观察说明](visible/final-1/observations-root.md.txt)、[独立审图与完整性](review/f5-native-5d56187-independent-review.md.txt)、[74 文件固定清单](visible/native-file-manifest.json)。

22 份观察包含失败尝试，不等于 22 次成功动作：08 的文件名虽写 saved，实际文件对话框拒绝路径，09 才成功保存；18 在编辑区外无焦点，Ctrl+Z 未触发，19 工具栏 Undo 成功。原图、错误标签和说明一起保留。定时状态快照可能滞后，不以它代替实际图像和保存文件。

合成恢复/故障夹具、真实异常子进程恢复、Qt 自动测试、真实 Geant4 3+3 事件消费、原生观察分别计证，不能互相替代。Linux CI 不等同 Linux 原生桌面验收；本次不新增物理基准结论。

## 历史、协作和接续

旧候选 4f960ab、b290eb4 及 5d 的失败、已中止轮、原生失败尝试、修后收据均选取归档；原报告中的 pending/unknown 不追改。历史 301 项候选复制清单重验后 300 项仍匹配，一份可变 CI 状态文件的旧字节已不可恢复，原 pin 和异常说明保留，当前版本另存；不得把后者当作旧版本。两份更早不可复制条目仍见原 inventory。

DeepSeek 的实际贡献为前端设计咨询，回信见[设计收据](design/design-receipt.md.txt)；实现由独占文件写者完成，另人交叉复核，主负责人统一验收。没有将设计咨询称为 DeepSeek 实施或实窗验收。

已按固定清单保存2072个证据文件、17294016字节；原生74文件固定清单、CI567文件固定清单及历史pin分别复核。加入复制收据后暂存目录2073文件逐一与最终目录比对，见[字节发布收据](archive-verification.json)、[完整选择清单](selection.json)、[复制收据](copy-receipt.json)和[Windows基线门禁](windows/baseline-gate.log)。复制工具的 `phase_complete=false` 说明该工具不裁决阶段，不应改写；阶段结论由最终独立审查与本报告给出。[最终独立归档审查](review/f5-final-archive-independent-sol.md)已通过：2072项源/副本、四ZIP/521成员、13份正式报告及全部严格F4基线核验一致；[详细收据](review/f5-final-archive-independent-sol.json)。[首席关闭审查](../../collab/reviews/20261031-astra-f5-close-review.md)记录阶段判定与集成边界。

下一阶段仍按 ROADMAP 由用户启动。建议在 F5 完整收尾后以[交接文件](../../collab/20261031-f5-handoff.md)开新对话接续。J1 负责整体视觉、区域区分、布局和主题；设计可在 K1 期间先行，实施待服务/状态所有权稳定后与 I2 并行。主题稳定后统一易懂中文，F8 做跨页 DPI、键盘及可用性验收。
