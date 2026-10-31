# clean提交上的规范单例验收

完成：Windows及WSL Linux的 `static / k1_staging_alias` 规范runner均1 pass / 0 fail / 0 skip，严格门禁均exit0；未用allow-incomplete或裁剪旧baseline。原探索证据未覆盖。

冻结完整HEAD：`5644e1e52b9c2dd5b463217e9e601c8116f8a913`。两份report均git_dirty=false、git_status_porcelain为空、tracked_source_gate=pass；主工作区复核clean。

| 平台 | v3入口 | 报告 | 严格门禁 |
| --- | ---: | --- | --- |
| Windows CPython3.11.9 | 36 | windows-reports/20261031-204100-503276c4/report.json | Windows原件exit0 |
| WSL Ubuntu CPython3.11.18 / PySide6 6.11.1 | 33 | wsl-linux-reports-copy/20261031-204115-b1ea9108/report.json | Linux原件、Linux复制件、Windows复制件均exit0 |

父进程及每个规范子进程实际退出/命令/完整原始日志SHA见 `parent-process-receipt.json`、`wsl-native-process-receipt.json`、`formal-validation-receipt.json`。两个runner使用要求的 `--profile static --case k1_staging_alias --require-tracked-sources --fail-on-skip`；门禁不带豁免参数。

实际配置身份：

- 正式测试SHA：`0d5cb4db40d50417e16a316ec8825ddd30c7265a0b8d468679529288e9a95de2`。
- 产品 experiment_bundle.py SHA：`5c1dff0338e80a673ba8f3427aeb7bfe1abe9d2b5315efca564310be8118385a`，未改。
- Windows/Linux source_fingerprint均 `890635b6d521659e43cf735d07f862c6ebd5959e6c5ea68d023d55332a8a930a`。
- Windows/Linux tests_content_fingerprint均 `2402bc3c9d69b0696f46b2cd4d777239366c4508cd05e22b4bb6404306e6b0ea`。
- Windows report SHA `bbf6e7430e9c6ea78cf982afd2cb21eb901aa9cea3fc20cf00b791ba12f1fc29`。
- Linux report SHA `75cc78a08a66d085b203e614b334b62b23e5b3b7d0bc77ef162c8141b2eaf4d3`。

WSL原件在Linux本地 `/tmp/k1-p1-canonical-20261031-n7_ik251/reports`，保留。34个报告/日志/夹具文件逐SHA复制到本目录，全部相等，见 `wsl-copy-identity.json`。此前Windows挂载盘的fixture不支持既有renameat2发布，且共享工作树Linux git status等待文件系统RPC，因此最终使用同一真实提交的Linux本地临时detached源码副本 `/tmp/k1-p1-canonical-20261031-n7_ik251/source`；测试SHA和两类指纹与主工作区完全相等。source clone/checkout日志保留，不修改共享工作区/仓库配置。自有诊断进程已结束，相关会话52098/45155均已取得最终退出；正式父会话52369最终exit0。

两份规范报告backend_provenance均为 `backend executable is missing`；静态case不要求backend，本轮未构建、未调用旧exe、未执行Geant4模拟，不能声称有该HEAD后端构建或双Geant4版本运行。Linux只实测上表一个Python/Qt平台。

旧r2失败对照继续引用上一层 `exploratory-complete-receipt.json` 与 `windows-old-r2.log`：同一测试SHA、进程内载入旧r2真实产品SHA，正式测试exit1/33并准确失败在必须拒绝的新增assert。此负对照不伪装成规范成功报告。

最终状态：任务所需规范单例与防回归证据齐备，无运行会话。供root及独审终审、归档集成，不宣称整个K1阶段由本专项单独完成。
