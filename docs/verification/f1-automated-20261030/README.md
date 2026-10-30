# F1 自动验收归档：实窗待验，阶段未关闭

本归档保存产品冻结 `f176d0ed4cea60b7ca5a80ed81017c9404ec1257` 的自动验收证据、两个失败冻结的原件，以及独立审查和性能测量。**自动验收通过不等于 F1 全阶段完成；实窗观察仍 pending，尚未合入 codex 集成分支。** 后续实窗证据须另建归档，不追改本报告。

## 实现与兼容边界

新增输出身份与实际输入来源账本：构建 commit/源码指纹、实际读取字节 SHA、共享 execution_id、显式 run/thread 归属、关闭后产物 SHA/size。读取不等于语义接受或内核应用；运行成功、字节一致与物理验证分别判定。旧 metadata v1 仍兼容，新扩展损坏不得降级为旧协议；结果搬移只从当前根读取。

`format=auto` 为显式选择：最终 scoring 启用且 hits/event_edep 任一启用时选择 ROOT，其余 CSV；省略仍 CSV，不启用任何计分开关。GUI 身份及历史核验在后台执行，过期结果不得覆盖新请求，独立操作重新核验，合并前再验。

实现链：5373d57 来源身份；cd0f44a 自动格式与后台核验；3d1faf1 异步预设图选择修复；f176d0e GDML 分配失败句柄清理及跨版本故障测试修复。

## 当前冻结的自动验收

- [Windows 全量原报告](windows/final-1/report.json)：143 PASS / 0 FAIL / 0 SKIP，48511 个 v3 断言入口。逐项和总数对 E6 134 项 / 42,815 入口基线检查通过，零断言用例为空。
- [Linux 双版本实际 CI](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41028779177)：Geant4 11.3.2 与 11.4.3 各 143 项通过。
- [M0 实际 CI](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41028779326)：Windows 与 Ubuntu 各 64 项 static/GUI 通过。
- [CI 原始证据汇总](ci/ci-evidence.json)：12 份报告、414 条用例执行记录、4 个官方 ZIP 摘要及全部逐例日志核验。414 是跨平台执行次数，不是独立测试种数。
- [实际构建收据](additional/1-f1-gdml-build/receipt.json)：MSVC Release、Geant4 11.3.2、实际构建输入 Git 状态 clean。整个 CI 检出的 git_dirty 与构建输入 clean 分开记录，不补造 CI 工作区全干净结论。

| 平台 / profile | 用例 | 断言入口 |
| --- | ---: | ---: |
| linux-evidence-11.3.2 / backend | 59 | 40387 |
| linux-evidence-11.3.2 / gui | 39 | 2341 |
| linux-evidence-11.3.2 / integration | 20 | 4378 |
| linux-evidence-11.3.2 / static | 25 | 1373 |
| linux-evidence-11.4.3 / backend | 59 | 39795 |
| linux-evidence-11.4.3 / gui | 39 | 2341 |
| linux-evidence-11.4.3 / integration | 20 | 4378 |
| linux-evidence-11.4.3 / static | 25 | 1373 |
| m0-report-ubuntu-latest / static | 25 | 1373 |
| m0-report-ubuntu-latest / gui | 39 | 2341 |
| m0-report-windows-latest / static | 25 | 1364 |
| m0-report-windows-latest / gui | 39 | 2343 |

源码指纹 `db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc`；测试指纹 `57a80e4f5e73a2d07b5b834b6ca91ac482161622ca1d5e1d558cbd37d79b5f35`；程序 SHA-256 `f02d3bdc94121dcf35de05e152773fdec8c87f5c8759e53fd1f95d3f51f43ea8`。后续文档提交不冒称这个已测程序的构建提交。

## 已保存的失败与修复

- 首轮 cd0f44a：Windows141/143，两失败为开始页预设图丢失和遗漏既有 Geant4 数据目录环境参数；四 CI job 均在 gui_start_page 失败，Linux 后端/集成尚未执行。[首轮 CI 原汇总](history/ci-round-1-f1-ci-final/failed-round-summary.json)。实际等待后的反例确认是图表意图丢失，修复不只增加等待；原图表断言保留。
- 第二轮3d1faf1：Windows143/143、48,511入口及M0双OS通过；两个Linux版本的GDML故障测试遇到未捕获Xerces内存异常。[第二轮 CI 原汇总](history/ci-round-2-f1-ci-corrected/failed-round-summary.json)。进一步确定性实验复现原适配器四开三关；修复四开四关，Xerces读取故障五开五关。只接收明确两种分配异常，其余异常继续失败；原检查保留。
- 原报告、原日志及官方产物身份保持原字节；历史失败不进入最终绿色报告集合。
- 归档复核纠正了首轮旧README的一个记录错误：当时只有1份完整job日志真正落盘，另3份于本次从GitHub补收。[更正与补收摘要](history/ci-round-1-f1-ci-final/job-log-backfill-20261030.json)保存时间和SHA；旧README不追改。

## 实窗与未完成工作

最终代码的真实小运行已完成2线程、2轮各2/2事件，auto实际ROOT，20个登记文件的严格身份校验通过。该夹具用于后续窗口展示，**尚无本冻结的实窗截图、原生操作或host退出收据**。合成状态、真实模拟和窗口观察不得互相替代。

旧可见host曾被其他窗口遮挡；`sky.activate_window`及刷新选择后的恢复操作均返回 `failed to activate captured window`。依computer-use恢复规则停止重复输入，已请用户手动将目标窗口置前，尚待回应。旧host加载更早代码，不能拿它验收本冻结。下一步：取得可操作窗口、以最终冻结host补验身份/构建/输入/产物/历史关键状态与正常关闭，再独立复核并关闭F1、集成codex。

## 性能与证据保留范围

[54次格式对照](performance/1-f1-performance-before-auto/report.json)及[18次缓冲对照](buffer_performance/1-f1-buffer-performance/report.json)按历史原测量保留。hits样例F1 CSV中位5.724s/95.43MB、ROOT3.512s/50.61MB；256KiB缓冲没有稳定整体收益，候选撤回。结果包含启动/收尾与系统噪声，Python复核时间不是C++哈希CPU时间，不能外推任意模型或称为最终冻结重复测量。

DeepSeek实际前端设计回复及请求收据随归档保存；独立代码/实验/证据审查分别列入清单。额外Astra子代理曾因跨后端payload不兼容未启动，不列作已完成审查者。

归档为原字节复制并复核SHA、严格门禁和链接；原ZIP、程序及大CSV/ROOT输出留在清单注明的本机源位置，不能称为独立可移植实验包。历史Markdown以字面文本保留时使用`.md.txt`，原文字节不变。SHA不是签名，不能防数据和metadata同时被协调改写；不提供跨文件原子持久化或中断卡死IO保证。Geant4内部数据集/任意原生IO仍明确未观测；Q2物理验证、K1实验包、完整GUI编辑及安装包不随本归档完成。
