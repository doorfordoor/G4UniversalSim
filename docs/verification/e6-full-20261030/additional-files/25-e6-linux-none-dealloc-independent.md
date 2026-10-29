# E6 5bf479d Linux none_dealloc 不同写者只读复核

未编辑产品/正式测试，未安装依赖、未触发或重跑CI。三个完整原case日志复制到out/verification/e6-linux-teardown-review并核对原报告SHA。

## 原始CI事实

M0 Ubuntu：Python3.11.17，glibc2.43；两Geant4 Ubuntu24.04：Python3.11.18，glibc2.39。三者均393个assert入口、退出-6，Fatal Python error none_dealloc，runtime finalizing，Current thread <no Python frame>。没有原生backtrace，不能从这些日志断言具体C++模块/析构函数。M0 Windows Python3.11.9通过，PySide6/shiboken6安装日志明确6.12.0；M0 Ubuntu同样明确6.12.0。两Geant4 job的pip用了--quiet，未打印PySide版本，报告也无此字段，因此其6.12.0只能根据同时间同requirements解析作推测，不能说直接核验。未用glyph警告冒充崩溃根因。

## 与正常应用退出的比较

product app.py:30-38在app.exec返回后close/deleteLater/processEvents；冻结smoke:228-230也已有这三步，不是漏掉了所有teardown。旧Linux文档记录的QObject::~QObject -11问题已有明确本机gdb栈，那是历史另一失败，不能把它当本次none_dealloc的原生栈。当前smoke还持有widgets/bindings等子控件引用并反复读取currentData/itemData，普通app入口不做这种大量状态快照；是否具体引用寿命造成问题需实验，不能只加del就称修复。

## 已有可用WSL环境（本轮live核验）

Ubuntu WSL2原先Stopped，正常只读调用启动，未安装。
- /home/u123/g4ci/bin/python：3.11.18，PySide6/shiboken6/Qt6.12.0，matplotlib3.11.2，numpy2.4.6。与Geant4 CI的Python minor/version吻合；最小offscreen QApplication正常exit0。
- /home/u123/venv/bin/python：3.12.3，PySide6/shiboken6 6.12.0，matplotlib3.11.2，numpy2.5.4；不能用3.12通过替代3.11失败环境。
- g4env当前Python3.14.10且无PySide；g4env114 Python3.11.18但无PySide，不适合直接GUI复现，未安装。
- gdb已在/usr/bin/gdb；kernel core_pattern为/wsl-capture-crash管道，不能假定cwd存在可用core。

运行前设置QT_QPA_PLATFORM=offscreen与QT_PLUGIN_PATH=/home/u123/g4ci/lib/python3.11/site-packages/PySide6/Qt/plugins。repo在/mnt/c/Users/123/.codex/worktrees/effective-config/G4UniversalSim；纯GUI无需新Geant4环境或安装。具体本次原样命令/exit保存在wsl-frozen-original.json。

## 新的最小实验（不修改正式测试）

同一g4ci Python3.11.18 + PySide6/shiboken6 6.12.0下：原冻结smoke完整运行仍打印ok/G4USIM_ASSERTS=393后exit-6，完整stdout/stderr已存。

更小实验只有QApplication/QComboBox、无MainWindow/Matplotlib/Geant4/正式assert探针：combo.addItem(test)后读取缺失userData的currentData，100次None refcount从5373到5274，随后1000次从5272到4272；正常解释器finalizing也none_dealloc exit-6。日志none-refcount-probe.log。该行为指向Qt binding在缺失userData->None返回路径的引用计数问题，而不是由393assert业务判定本身造成；具体绑定实现归因仍可由frontend用本机gdb/小实验确认。

对照实验记录getter-controls.json：currentText、带实际字符串userData的currentData、缺失itemData分别独立进程正常teardown，比较None refcount与退出。建议frontend优先查widget_state中的currentData/itemData大量读取；不建议os._exit、吞掉-6、只数assert或仅据字体warning修复。任何改法都必须保留状态/业务断言，并在同3.11 Linux进程自然退出0及完整suite验证。

新目录e6-ci-release尚未创建/冻结/触发；等root新SHA后另采，不覆盖两次失败。
