# I2 UI 两项P2修复窄独立审查（2026-11-01）

结论：事务重开修复及显式candidates队列修复通过；发现1个仍需修复的P2自动候选丢失边界。只读审查产品，未改产品和原测试；新探针仅写out/collab。

## P2：自动发现进行中发布安装，会丢掉自动候选

定位：gui/g4usim_gui/widgets/environment_dialog.py:360-364，关联151-160、177-180。默认_candidates=None表示core/environment_discovery.py:348-355自动读取G4USIM_EXE/PATH。refresh开始时清空facts；此时安装publication进入_installed_candidate，取facts为空，构造candidates=[新安装]并覆盖None。旧发现完成后pending触发第二轮，但第二轮只传[新安装]，既不自动发现旧环境，也不合并首轮完成facts，导致已有环境消失于选择列表。

真实异步探针（原venv/Qt offscreen）通过两个threading.Event控制首轮discover返回，在其busy期间触发publication，记录传入discover参数：第一轮null，第二轮["new-backend"]；第一轮返回的old-backend不在最终_candidates中。原测试smoke_i2_install的busy覆盖只从已经显式_candidates列表追加，因此没有覆盖这个默认路径。建议保留自动发现语义，或将首轮自动候选事实与新增候选合并后重探测，并补默认None的真实异步回归。

## 已通过范围

- environment_dialog.py:354-370 对既有list/tuple/单候选保留追加；忙时pending且完成/失败后各触发fresh refresh，没有自动选择/启动模拟。关闭保护保留。
- install_dialog.py:235-241 在transaction_exists时调用core inspect_transaction；252-257恢复plan/target/receipt。原smoke实际取消、重开窗口后resume/discard启用、恢复同plan SHA并发布通过。
- core/environment_install.py:892-918 检查持有OS锁、journal prefix/root/transaction id、plan digest与release契约；legacy无plan返回discard-only。额外真实旧journal实验通过：从取消事务journal移除plan后重开Dialog prepare_plan，resume disabled、discard enabled。没有放宽执行/清理门禁。

## 验证

使用D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe、QT_QPA_PLATFORM=offscreen，无task-local 3D runtime。
1. gui/smoke_tests/smoke_i2_install.py：退出0。
2. out/collab/review_i2_ui_fixes.py：退出0，真实异步None候选遗漏与legacy实际journal复验；结果out/collab/i2-install-ui-fix-review-evidence.json。
3. 未全项目重审、未实窗、不宣称I2整体验收。
