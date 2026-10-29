# E6 Windows 可见验收计划 — 5bf479d（仅准备，未启动）

冻结提交 `5bf479d85ba7c12e0f71984d31b8335c47c5a8c3`。此计划及checkpoint只在out中；不改tracked文件，不干预session55580或CI。

## 启动前硬条件

1. 等用户**明确回复已解锁**，root通知后才launch。当前无该回复；不调用Computer Use、激活窗口或试探锁屏。若恢复后图像仍为锁屏，立即停止，不尝试绕过。
2. 重核HEAD/dirty及最终冻结报告中的exe身份。当前manifest里的exe只是候选文件哈希，不能据它单独声称构建对应5bf479d。优先在现有全量/CI终态后做轻量执行，不占用正在构建或被替换的exe。
3. 阅读/复用computer-use技能，node_repl + @oai/sky；用fresh list_apps/list_windows选出本轮唯一标题`E6 Windows acceptance 5bf479d`。不复用旧窗口ID，不操作用户其他窗口。
4. 数据全部在本目录新子目录。真实writer准备样本与UI点击分开记：准备样本是程序化文件操作，不能写成用户经GUI逐字段输入。每步记录输入/输出哈希、实际动作、native截图观察、错误与下一步。失败先查当前状态，不盲目重放写入。

## A 迁移预览与拒绝覆盖

- 显示中文迁移预览：旧项目v5→v6；另检查主INI缺省→1及几何旧格式→2（模板和显式metadata映射只用既有编辑子集）。读取可见版本、改动、诊断/输出预览、格式检查不等于模拟验证的说明；轻/深主题各检查一次可读性，键盘可达按钮。
- 先预览，再从可见“写入新副本…”选择未存在目标；确认成功后当前项目不自动切换，只有显式打开项目副本才切换。
- 分别选择原文件、已占用目标、原文件硬链接，预期拒绝；原件/占用目标SHA保持。记录UI错误与按钮状态，不删除原件，不把拒绝理解成写成功。
- 损坏/未来版本输入失败后不能混入旧预览为新数据，写按钮应禁用；窗口/当前项目状态保留。截图须实际观察内容，不能以文件存在替代观察。

## B 真实运行包快照恢复

- 用冻结真实create_run_package准备混合材料配方、已编辑几何、source/physics/scoring参数及未输出禁用草稿。使用已核验backend路径；不要直接照搬测试fixture的sys.executable作为Geant4程序。
- 准备后改变原外部输入，再从可见历史页“Load Snapshot into Project”进入。确认读取包内当前材料/几何及快照编辑参数；未输出草稿不伪造恢复。
- 当前配置页“消息与文件”恢复详情应立刻可见，运行日志也保留notes；成功无强制information/exec模态。可见中文说明须包括重新校验/生成、不恢复手改主配置/宏、草稿、历史成功，当前hash不证明历史run字节相同。
- 普通Open仍不能把envelope当普通项目。历史入口遇坏metadata、缺包资源或不可表示数值，warning且旧项目/路径/页面/包状态保留。
- 保存为新的普通项目，重新打开并再次生成；比较材料/几何及S/P/S参数，原包/原源不改。纯旧式project-only快照须显示“原资源/历史结果未核验”，不能称恢复了包内输入。

## C 复制输入与实际命令身份

- 源标准包main真实threads2/seed43/name=writer_run；当前UI改为7/999/unrelated。在历史页复制（先不运行），检查新包路径和外部输入模式，命令预览应是2/43/writer_run，backend仍为当前所选exe。
- 点击Run后由真正Inspect回执继续；若执行D则记录runner实际进程程序/arguments及workingDirectory；若不执行D，只能记“预览/预检命令已观察”，最终启动命令沿用已通过offscreen证据，不能声称可见真实执行。
- 另用seed省略、seed0、main参数不同于snapshot及名称含内部Unicode/尾NBSP的标准包，核对CLI。字段来源只取当前严格验证main。ASCII外围空白按既有INI语义去除，其他Unicode保留。
- 线程不可投影时，若副本已创建，提示须为“副本已创建，未载入、未运行”，给出路径；旧current和进程不变。准备期非法seed拒绝则仍普通复制失败。

## D 可选轻量真实2事件（条件适合才做）

- 仅用本目录的独立标准包、1或2 worker、2事件，选简单box/普通材料/已支持点源；不启动旧Q1脚本的20事件+千万事件取消流程。
- 先确认无同一exe重建/替换；通过可见Run入口真实Inspect→Run。记录配置输入、exe哈希、最终CLI、日志、run_summary/metadata与完成事件数，最多等待既有90秒级上界，定期报告状态。异常先检查自身进程/会话与输出，不能超时即重跑。
- 成功至少正常退出、独立run_result success、本次新summary、planned=completed=2，run总数与逐run一致。线程/seed只按真实证据报告，不要求两个worker都分到事件，不用命令预览代替实际应用证据。
- 这是执行/工程往返证据，**不是物理正确性、一般无偏性或跨平台逐位复现验证**。

## 证据与关闭

- Native截图由@sky选定自身窗口获取并直接观察，报告写出所见文字、布局和状态。若API返回锁屏，停止。QWidget.grab可额外保存布局图，但永远单列为自渲染参考，不能替代可见窗口证据。
- 最终记录：每项pass/fail/pending、root确认的冻结身份、原件/副本哈希、最终命令、真实2事件是否执行及其报告路径、剩余边界。只关闭本轮自身窗口/进程，不按进程名杀其他任务。

## 已有脚本检查点（禁止现在启动）

- `out/collab/e6-visible-check.py`：仅旧v5迁移对话框样本，300秒自动退出；窗口grab是自渲染，不覆盖snapshot/duplicate；无解锁授权门。不得因它会show而直接重跑。
- `gui/smoke_tests/smoke_project_snapshot_restore.py`：真实writer往返fixture/断言参考，主要offscreen；它的默认exe是Python，不能用作D的真实Geant4运行样本。
- `gui/smoke_tests/smoke_duplicate_history_cli.py`：实际Run入口命令构造参考；合成inspection回复且拦截进程，不能当D的执行证据。
- `gui/smoke_tests/smoke_q1_windows.py`：20事件及千万事件取消/关闭验收，范围重；本轮不直接启动，不把其截图当E6窗口验收。
- 原有`e6-migration-qt-layout-zh.png`/`e6-migration-visible-zh.png`只作布局参考；先前native图像是锁屏，E6可见验收仍pending。

下一动作：保持待命；只在用户明确解锁、root明确允许launch后，准备本轮fixture并启动唯一窗口。
