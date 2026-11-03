# J3 整体验收 P2：状态标签文字对比度修复（作者侧冻结证据）

- 状态：**作者侧修复与冻结候选证据完成；J3 仍未关闭**，须由独立复验再次确认。
- 候选提交：`c082ecccfee3e54155a5eed82bd1748057e8356a`（`fix(gui): keep status chip text readable on its tinted veil`）。
- 触发来源：`docs/verification/j3-whole-review-20261103/README.md` 与用户转达的整体验收结论——状态标签把语义色直接画在各自 veil 上，B/K/苔原的成功文字实测 4.345/4.345/4.310:1，低于正文 4.5:1。

## 1. 改了什么

- `gui/g4usim_gui/core/theme.py`：新增 `veil_text(foreground, background, minimum=4.6)` 与 `status_combinations(colors)`。前者把语义色向可读锚点（黑/白中对比度更高者）混合到指定下限并保留色相，产出 `success_text`/`failed_text`/`warning_text`/`running_text`；后者给出每个状态标签最终的文字/背景组合。
- `_base_stylesheet` 与 `_design_stylesheet`：成功、失败、运行中的 `statusChip` 文字改用 `$success_text`/`$danger_text`/`$running_text`，背景仍是各自的 veil；中性 chip 不变。
- 测试：`scripts/test_theme_registry.py` 增加最终混色组合 ≥4.5 的断言（含统计组合）；`gui/smoke_tests/smoke_theme_response_shell.py` 对 15 种皮肤渲染真实 `statusChip` QLabel，读取 polish 后的文字色并采样渲染背景像素，断言与 `status_combinations()` 一致且对比度 ≥4.5。

## 2. 冻结方式

候选提交之外的文档改动不属于产品候选，因此证据不是从日常主工作区（含用户已有的超长路径删除记录、未跟踪交接材料）直接采集，而是：

1. `git worktree add` 一个该提交的干净检出（路径见 `directed/clean-worktree.txt`），启用 `core.longpaths=true` 以免 Windows 260 字符限制把仓库内的长路径证据误报成删除；
2. 复制 gitignore 的 `gui_runs/` demo 输出作为 `gui_theme_state` 的输入夹具（该用例要求默认项目输出树非空）；
3. 在该检出内用与主工作区相同的 GUI venv 和同一后端可执行文件跑三个 profile；
4. 复制 `report.json` 与逐用例日志到本目录，运行 `scripts/check_report_evidence.py` 复核。

因此三份报告的 `git_head` 均为 `c082eccc...`、`git_dirty=false`，`source_fingerprint` 一致为 `9e40e889d49a...`，`tracked_source_gate=pass`，`assert_probe=settrace_assert_lines_v3`，`log_digest_algorithm=sha256_raw_bytes_lf_v2`。

本次未重跑 backend profile：改动只涉及 GUI Python（主题/样式表/测试），没有 C++、计分或物理变更；backend profile 与 11.3.2/11.4.3 双版本矩阵沿用既有已归档证据。

## 3. 结果

| profile | 用例 | 结果 | 断言 |
| --- | --- | --- | --- |
| static | 49 | 49/49 通过 | 5 687 |
| gui | 76 | 76/76 通过 | 10 535 |
| integration | 33 | 33/33 通过 | 6 830 |

合计 158 例、23 052 断言、0 失败、0 跳过；门禁 `check_report_evidence.py` 三个 profile 均通过。

独立验收探针（`probe/status-contrast.py`，来自 `docs/verification/j3-whole-review-20261103/`）在同一干净检出复跑：退出码 0，输出 `[]`，15 种皮肤全部 ≥4.5:1，实际最小值 4.605（botanical/苔原），最大 10.144。探针本轮完整结果在 `probe/status-contrast-after.json`，各皮肤渲染截图在 `probe/replay/`。

## 4. 复现

见 `directed/clean-worktree.txt`（工作树核对、python/后端路径、三条 profile 命令、`gui_runs` 夹具说明）。探针复现：

```
cd <clean-worktree>
D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe -B docs/verification/j3-whole-review-20261103/status-contrast.py
```

## 5. 不证明什么

- 本证据只覆盖本机 Windows（10.0.26200，Python 3.11.9，PySide6 6.11 系列）三个 profile；不代表 Linux 实桌、125%/150% 真实操作、完整状态矩阵等 J3 其余退出门禁已完成。
- 渲染截图与探针采样证明当前实现的实际像素/调色板值，不证明这些文字在其他平台字体、缩放或系统主题下同样达标。
- 三份报告来自干净检出，但证据目录本身是之后单独提交的；候选产品身份以 `c082eccc` 为准，文档提交不改变产品身份。
- 本证据不使 J3 关闭；是否关闭由独立复验决定。
