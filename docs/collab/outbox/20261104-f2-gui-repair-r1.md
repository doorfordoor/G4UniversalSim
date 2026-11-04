# F2 GUI 首候选修复 R1（作者自测，冻结待独审）

任务 ID：F2-GUI-REPAIR-R1。冻结候选：`9c12100db57d24ef7dc53436362c6f72686c4105`
（C 盘独立检出 clean，Windows 重编通过，C++ 指纹
`c0559899899485d466bb0fc912bb09aa52565423e6713e7b613f86cc46949e76`）。本修复只动
GUI 模型/客户端/面板/测试与词典，不改 C++、旧业务、旧断言门槛、CI，不重编未变后端，
不扩截图/启动器/状态矩阵。

作者完成自测后即冻结：**未提交 Git、未推送、未切换分支**。ROADMAP/STATUS 由主审收尾。

## 1. 修复项与判定标准

### 1.1 能量单位与换算结果（`gui/g4usim_gui/core/session_model.py`）

缺陷（主审反例，原件 `out/collab/f2-gui-independent-r1/model-state-report.json`）：

- `parse_energy_text('1 meV')` 返回 `1.0 MeV`：旧实现把单位文本一律转小写，毫（milli）
  前缀被误认成兆（mega）前缀。
- `parse_energy_text('1e308 TeV')` 返回 `inf` 且无错误。
- `parse_energy_text('1e-323 eV')` 返回 `0` 且无错误。

修复：

- 单位改为**区分大小写的规范拼写**白名单：`eV`、`keV`、`MeV`、`GeV`、`TeV`；无单位
  保持历史默认 MeV。`meV`、`mev`、`MEV` 等歧义/非规范拼写直接以 `energy_unit` 拒绝，
  不新增单位种类。
- 数值换算后必须 `math.isfinite(mev) and mev > 0`；溢出（`inf`）与下溢（`0`）在前端以
  `energy_range` 拒绝，绝不把 `inf`/`0` 发送给后端。
- 为拒绝信息补最小中文词典（`energy_empty/energy_number/energy_unit/energy_range`
  及对应英文提示），面板 `set_rejection` 统一经 `ui_text` 翻译，不显示裸错误码。

### 1.2 当前后端版本号回退（`gui/g4usim_gui/core/session_client.py`）

缺陷（同一 Client）：先接受 `state_revision=5`，再接受旧 ack 携带的 `3`，snapshot 当前值
回退到 3。服务端缓存 ack 保留操作时旧 revision，reader 取消 ack 与主线程终态也可能并发
发布，下一次合法请求将携带过期版本。

修复：

- 新增 `session_model.next_revision(current, candidate)`：只前进不后退；忽略 bool、负值、
  非整数与 `None`；非法 current 归一为 0。
- `SessionClient._adopt_revision()` 与 `apply_state()` 统一走该函数；旧回执仍按原样保留
  在历史/收据中，只改“当前已知 revision”。
- 新会话 `start()` 仍重置为 0；不同会话的 revision 不互相比较。

## 2. 修改文件与哈希

| 文件 | 变更 | sha256 | bytes |
| --- | --- | --- | --- |
| `gui/g4usim_gui/core/session_model.py` | 修改 | `5859c6f11d1532c12f28a3f4ea66de21bc766ac7463e39561fc864630eba836f` | 14,251 |
| `gui/g4usim_gui/core/session_client.py` | 修改 | `62b7e778a1973223e35aa57e3cc7c51d6f3facb801887e46029c25cad0d0f6ab` | 29,083 |
| `gui/g4usim_gui/widgets/session_panel.py` | 修改 | `276999a28b2e5c58f06edbaf66ca39c43556a8a945d8eacb3a6b172c427b2ed8` | 28,487 |
| `gui/g4usim_gui/core/i18n.py` | 修改 | `effad843cc430fe43a5a5d52b2fbcad606b1b0ffe1028a5f063fa53405073189` | 144,345 |
| `gui/smoke_tests/smoke_session_panel.py` | 修改（回归） | `cf26756ea482b9745c5dce2ee555732d82f1bda4f9530a575200c73466f37312` | 15,001 |

## 3. 自测证据

聚焦回归（受影响模型/会话控件 + 真实会话接线）：

`out/verification/f2-gui-repair-r1/20261104-160346-4b17780b/report.json`

```
5 pass / 0 fail / 0 skip of 5 cases
assertions executed 212（gui_session_panel 81、gui_session_backend 44、
gui_history 9、gui_run_result 27、gui_main_window 51）
probe settrace_assert_lines_v3, source c05598998994..., tests be1809d13684...
```

`python -B scripts/check_report_evidence.py --report-root out/verification/f2-gui-repair-r1`
→ `report evidence: OK`。

新增/更新的回归覆盖：

- 能量正例：`100 MeV`、`50keV`、`1.5e2 MeV`、`2 GeV`、`1 eV`、`1 keV`、`1 TeV`、无单位
  `100`；错误例：空、非数字、`50 banana`、`-1 MeV`、`0 MeV`、`inf MeV`、`1e999 MeV`。
- 主审三反例：`1 meV`→`energy_unit`、`1e308 TeV`→`energy_range`、
  `1e-323 eV`→`energy_range`。
- revision：`next_revision` 纯函数（前进/忽略 bool/负值/None/非法 current）；
  `SessionClient` 实例级“5 → 旧 3 不回退 → 6 前进 → 新 start 重置 0”。
- 真实会话接线：`gui_session_backend` 44 断言通过（三轮、拒绝、取消、关闭）。
- `gui_main_window`/`gui_run_result`/`gui_history` 未受影响并保持通过。

## 4. 身份

- 分支 `roadmap/F2-controlled-session`；HEAD `9c12100db57d24ef7dc53436362c6f72686c4105`
  （冻结候选）；工作树含本修复改动（dirty），用户/主审维护的文档改动保留未动。
- 后端 exe（未重编，C++ 未变）：`build_vs2026/Release/G4UniversalSim.exe`
  sha256 `01e3ae27a213be61732852a4b53afa5d53d1bdb926728390826a19487aeeeced`
  （2,678,784 B）；`--capabilities` 指纹 `c0559899…`、`build_git_commit=3f665ce1`。
  与主审 C 盘重编的 C++ 指纹一致；本修复不改 C++，故未重建。

## 5. 未验证与限制

- 两个修复均通过模型/客户端单元与真实会话接线回归；**未做原生 GUI 实窗输入操作**
  （主审将统一完成 Windows/Linux 原生与缩放验收）。能量反例在 GUI 输入框中的完整
  交互路径由主审实窗覆盖；作者只验证解析器、拒绝消息渲染与真实会话接线。
- 旧 ack 并发发布的回归为客户端状态机级模拟（服务端缓存 ack 时序无法在真实后端稳定
  注入）；真实服务端并发 acks 由主审独立复验。
- 修复不改变任何成功/收据判定，也不新增协议字段或单位种类。
- 其余 F2 限制（断线重连、完整 RNG 重放、MT 大物理取消）仍按固定清单推进，本任务不扩。

## 6. 复现

```bash
# 无需重编 C++（本修复只改 Python）
QT_QPA_PLATFORM=offscreen gui/.venv/Scripts/python.exe -B scripts/run_m0_tests.py \
  --profile all --case gui_session_panel --case gui_session_backend \
  --case gui_main_window --case gui_run_result --case gui_history \
  --executable build_vs2026/Release/G4UniversalSim.exe --report-root out/verification/f2-gui-repair-r1
python -B scripts/check_report_evidence.py --report-root out/verification/f2-gui-repair-r1
```

## 7. 冻结声明

作者实现与自测到此结束：不提交 Git、不推送、不切分支、不再扩展截图/工具。等待主审
独立复验；随后按原 F2 清单继续完整 RNG 重放。

## 主审身份勘误（保留作者原报告）

上文“与主审C盘指纹一致”的说法撤回，源自主审早期引用错误。作者构建c0559899与C盘独立clean 9c构建497e02ec是两个原始字节指纹；全部C++输入仅SessionServer.cc存在CRLF/LF差异，规范化内容相同。原报告及其指纹保持原样，勘误证据out/collab/f2-gui-independent-r1/build-line-endings.json。
