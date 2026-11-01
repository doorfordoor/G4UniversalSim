# I2 UI 剩余P2修复独立复审（2026-11-01）

结论：本轮限定范围未发现新的阻断问题；前轮自动候选丢失P2可关闭。未修改产品或正式测试。

## 源码复核

- core/environment_discovery.py:337-360 新additional_candidates在每次自动发现G4USIM_EXE/PATH之后追加，None仍保留自动发现语义；后续原有resolve后的path+env+sdk_roots去重保持不同激活事实，未按文件名粗暴合并。
- widgets/environment_dialog.py:63-65 保存_candidates=None及独立_additional_candidates；165-170 worker拿到本轮追加项快照；357-382 publication在忙时排队，自动候选不转成显式列表，显式候选仍追加保留；browse复用同一路径。
- widgets/environment_dialog.py:177-205 pending在成功/失败终态启动下一次fresh观察，旧facts不发布为最终事实；done使_closed/generation失效后迟到回调被拒绝。关闭后的publication最多改变已关闭对话框的本地追加列表，不触发发现或选择，无外部动作。

## 独立验证（原虚拟环境、Qt offscreen）

1. D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe gui/smoke_tests/smoke_i2_install.py：退出0。检查新增真实thread延迟测试确实经过root实际discover_environments，而不是把预期最终facts直接灌给UI；old/new共同保留。
2. 自建只读产品探针out/collab/review_i2_ui_final.py：退出0；证据out/collab/i2-install-ui-final-review-evidence.json。
   - core自动a + additions[a,b,b]只probe a/b两项；随后自动环境改成c，再发现得到c/b，证明自动来源fresh且未冻结旧a。
   - UI重复publication与browse同一b只保留一个追加项，_candidates仍None。
   - 关闭后publication及迟到success/failure不触发refresh、不填facts。
   - 真实worker阻塞时关闭后再publication，释放worker后总discover调用仍仅1，不启动第二轮。
3. 上轮已通过的现代journal重开恢复、legacy无plan discard-only结论保持；本轮没有扩大为全安装core或全项目审查。

证据边界：独立源码/Qt异步与I2 UI专项检查，不含整窗视觉、完整正式矩阵、干净系统安装、SDK实际编译或物理验证。
