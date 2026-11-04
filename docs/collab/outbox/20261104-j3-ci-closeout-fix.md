# J3 CI 收尾修复回执（2026-11-04，作者交付，待主审独立复验）

候选基线：`4eebbe9e2003c8b0ea6d5fac48df9e9cfa746e67`（主审提交的 8 文件候选）。
本回执只涉及三个文件，未提交、未推送、未改其它产品/测试/CI、未占桌面、未安装任何依赖。

| 文件 | SHA-256 |
| --- | --- |
| `.github/workflows/m0-static-gui.yml` | `cf8e17c3920c3652cd82db991a377a6ab205f5edbeb12f2502add5a570a843a0` |
| `gui/smoke_tests/smoke_config_agent_panel.py` | `713619a3848e2637702396c824042f9c7ffccccf62e61b7bcf864b49a05b467e` |
| `gui/smoke_tests/smoke_theme_state.py` | `beb0f0d68753b19f6418175f8749ce414c00e0a4e1a921960bda65b564fff181` |

## 1. 反例一：自然导航 footer 的 1 像素越界

CI 注解：`gui_config_agent_panel` → `smoke_config_agent_panel.py:321`（`full_in_scrolls`），
`('Export agent bundle','workspaceShellScroll',QRect(370,501,186,34),QRect(0,0,748,534))`，底部 535 超出 534 一像素。

根因（两层）：

1. 初段 footer 循环发生在已有的“显示专用夹具”之前（`prompt_edit.setPlainText` +
   `set_state({'allowed_actions': list(ACTIONS)})`），当时 Submit/Create/Export 等按钮是 disabled，
   对它们执行 `setFocus()` 不会成功，因此不能把失败归因于产品 FocusIn 链失效。
2. 合同只保证当前 focused-target 可见，不保证整组 footer 同时同屏（`gui/AGENTS.md`）。
   在 CI 字体度量下 shell 内容比视口高 1 像素，未获得焦点的 footer 按钮因此越界。

修复（不弱化判据）：

- 把上述显示专用固定夹具前移到 footer 检查之前（后续真实 Tab 遍历复用同一夹具，不重复注入）；
- 初段逐个按钮：保存 `prompt_edit` 焦点 → `button.setFocus()`（真实焦点事件）→ `settle()` →
  原样调用 `full_in_scrolls(button)`（精确矩形判据，无容差、无放大窗口、无隐藏按钮）→ 恢复 `prompt_edit` 焦点；
- 保留后续真实 `QTest.keyClick(Tab)` 遍历、`all buttons seen`、矩形/标签联合判据与
  `submit.count()==0 and actions.count()==0` 等断言。

本地代理反例（同一类“内容高于视口”条件，窗口高 600 而非 640）修复前：

```
AssertionError: ('Export agent bundle','workspaceShellScroll',
                 QRect(364,477,189,34), QRect(0,0,748,498))
```

修复后同一代理用例通过（`out/collab/j3-ci-closeout-fix/evidence/local-proxy-760x600.log`），
真实 760×640 用例在 Windows 与 Linux 均通过。

## 2. 反例二：`gui_theme_state` 依赖被 gitignore 的 `gui_runs/demo`

CI 注解：`smoke_theme_state.py:40`，`rows>0` 实际为 0；干净云检出不含 `gui_runs/demo`（`.gitignore`），
主审本机复制 `gui_runs` 后用例即 77/10822 通过，证明是隐含夹具依赖。

修复：

- 使用已跟踪的 gallery 输出 `examples/gallery/shielding_slab/output` 作为 Results 树夹具
  （`output_page.set_output_dir(...)`），不读任何用户历史；
- `set_output_dir` 经 evidence job 异步刷新，Linux 9p 上实测约 5 秒才出现行；
  改为**有界 20 秒**等待（`time.monotonic` deadline、`processEvents` + `QTest.qWait(20)`），
  超时仍以原 `assert rows > 0` 失败；
- 不改动其后任何选择/皮肤切换/状态保持断言。

## 3. Windows 云 CI 的原生 3D 渲染

`m0-static-gui.yml` 现在安装 `gui/requirements-3d.txt` 后，`gui_3d_view` 在 Windows 走真实
`windows` 平台分支，因 runner 无 OpenGL 驱动而失败：
`vtkOpenGLRenderWindow ... Failed to initialize OpenGL functions!`。

修复：在“Install GUI dependency”之后追加一个 **Windows-only** 步骤，
固定 `pyvista/setup-headless-display-action` SHA
`9c1c7435d9635423c90d2c37489588c81673274a`，输入 `pyvista: false`、`qt: false`、
`mesa3d-release: '24.3.0'`。

复核（只读上游）：

- `action.yml`（同 SHA）确认 `mesa3d-release` 仅 Windows 使用，默认 24.3.0；
  `pyvista: false` 时不写 `PYVISTA_OFF_SCREEN`，真实渲染窗口路径保留；
  `qt: false` 跳过该 action 的 Linux Qt 包。
- `windows/install_opengl.sh`（同 SHA）下载 `mesa3d-24.3.0-release-msvc`，执行
  `systemwidedeploy.cmd 1` 与 `7`，即仅在**一次性 GitHub runner** 上系统部署 Mesa OpenGL。
  用户主机不受影响，也未引入任何对象模式/跳过路径；`QT_QPA_PLATFORM` 与
  `smoke_3d_view` 的 Windows 真实分支保持原样。
- `actionlint .github/workflows/m0-static-gui.yml` 通过。

## 4. 自测证据（真实执行）

命令与身份：

- Windows：`D:/Geant4/G4UniversalSim/gui/.venv/python.exe`（Python 3.11.9、PySide6 6.11.1、Qt 6.11.1、Windows），`QT_QPA_PLATFORM=offscreen`。
- Linux（WSL Ubuntu，`/mnt/d/Geant4/G4UniversalSim`）：`/home/u123/venvs/g4-j3-native-20261103/bin/python`（Python 3.11.18、PySide6 6.11.3、Qt 6.11.3，`fc-match sans-serif` = 文泉驿正黑）。
- 候选：`4eebbe9e`；上述三个文件本地修改（`git status --porcelain` 仅这三项）。

Windows 官方 runner，两用例：

```
python -B scripts/run_m0_tests.py --profile gui \
  --case gui_theme_state --case gui_config_agent_panel \
  --report-root out/collab/j3-ci-closeout-fix/evidence/runner2
→ 2 pass / 0 fail / 0 skip, 1241 assertions, exit 0
```

报告：`out/collab/j3-ci-closeout-fix/evidence/runner2/20261104-*/report.json`；
`PASS gui_config_agent_panel: asserts=1227/118`、`PASS gui_theme_state: asserts=14/14`。

Linux（WSL，直跑脚本，offscreen）：

```
smoke_config_agent_panel.py → exit 0（L1 … PASS）
smoke_theme_state.py        → exit 0
```

日志：`evidence/win-*.log`、`evidence/linux-*.log`。

## 5. 未做与边界

- 未运行完整 GUI/static/backend/integration 矩阵，未触发云 CI，未提交/推送。
- 未修改 `smoke_3d_view.py`、`gui/g4usim_gui/*` 产品代码或其它 workflow。
- Windows`gui_theme_state` 在退出时的 tempfile 锁清理问题本次未单独改动：
  修复反例二后本地两平台均正常退出（exit 0），但云 runner 的一次性环境仍以主审实跑为准。
- 云 CI 是否转绿需主审推送后以真实 run 判定；本回执不预填 PASS。
