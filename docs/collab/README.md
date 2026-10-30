# 跨代理协作信箱（Codex/Astra ↔ DSH/DeepSeek）

2026-10-31更新：子任务按[项目协作模型分配](MODEL-POLICY.md)选实际可用模型和推理档；6.1 Sol为默认开发者，Astra负责必要的架构/科研疑难主审，Terra/Luna按当前可用性分派，不将计划角色冒称实际调用。正在运行任务完成后交接，不重做已有验收。

本目录是**两个代理之间的文件信箱**。谁在第几轮说了什么不靠粘贴，靠这里的文件和仓库本身。
阶段状态仍只由 [ROADMAP.md](../ROADMAP.md) 维护，功能支持等级仍只看 [功能支持矩阵](../功能支持矩阵.md)；
本目录不改变任何验收标准，只记录交接内容。

## 角色（2026-10-29 用户授权更新）

| 代理 | 位置 | 职责 |
| --- | --- | --- |
| Astra | Codex（主负责人、总设计师与首席审查者） | 规划、分工、实现集成、复杂诊断、科学方法与最终证据审查 |
| Sol 等子代理 | Codex 同一任务的明确文件范围 | 核心实现、测试及交叉审查；不得并发写同一文件 |
| DeepSeek | DSH 或用户授权的 API | 前端（GUI 交互/视觉/信息架构）设计负责人；按分配范围实现与验证，建议由 Astra 核对真实接口后集成 |
| 主负责人（用户） | 人类 | 拍板范围与优先级；在两个代理之间转发一句话即可 |

## 目录

```
docs/collab/
  README.md          本协议
  ASTRA-BRIEF.md     给 Astra 的当前状态简报（每次阶段收尾更新）
  inbox/             Astra -> DeepSeek 的来信与审查结论
  outbox/            DeepSeek -> Astra 的执行报告与待审清单
  decisions/         Astra 的设计决策与验收标准（一旦写入即视为约束）
  reviews/           Astra 的评审结论（按提交号命名）
```

文件命名：`YYYYMMDD-HHMM-<from>-<topic>.md`，例如 `20261028-0915-astra-stage1-scope.md`。
每条消息开头写：提交/分支、涉及文件、结论、待对方动作。**只写结论与依据，不复制整段会话**。

## 单写者规则（重要）

同一个文件同一时刻只能有一个写者。2026-10-29 起用户授权 Astra 完全主导；先前“Astra 只能出提案”的角色限制已由此授权更新：

1. Astra 在隔离 worktree 中负责 2C 集成，原 `D:\Geant4\G4UniversalSim` 保留给已有 DSH 工作；合并前须重新核对双方 HEAD 和未提交改动。
2. 仍先在 `docs/collab/inbox/` 保存范围与验收标准。Astra 可直接实现或分配给 Sol/DeepSeek，不再要求用户逐片转发许可。
   各代理明确独占文件；只读审查可并行，正在完整回归时冻结代码和测试。
3. 任何一方开始写之前，先 `git status --porcelain`；不为空的非自己改动一律不碰、不覆盖。

## Q1 全链路负责制（2026-10-29）

当前主对话负责 Q1 的全模块范围、审查、反例复现、修复、回归与最终验收，不以隔壁全部审完为开工条件。已有独立审查按提交号及变更影响复用，缺失模块由本对话分配；同一实现不能仅靠实现者自评关闭，须有其他审查者核对输入/代码/证据。隔壁仍可独立发现和复核，不自动成为主对话的待执行指令，也不因本规则被擅自停止或修改。

问题使用 R-xx/V-xx 编号，完整阶段用 Q1 等代号；问题修复提交与阶段关闭区分。当前正式编号、范围和退出门槛见 [ROADMAP](../ROADMAP.md)，此处不复制状态清单。计划只定义后续动作，不代表全模块审查已经完成。

## 会话互读（补充手段，不是主通道）

- DeepSeek 读 Codex/Astra 的会话日志：`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`（JSONL，含用户/助手消息与工具调用）。
- Astra 读 DeepSeek 的会话日志：`~/.dsh/sessions/<workspace-key>/<session-id>/session.v4.jsonl.zstd`（zstd 压缩）。
  由于 Codex 侧不便于解压，由 DeepSeek 导出摘要：

```bash
# 导出本会话摘要（只含用户/助手文本，不含工具输出与思考）
python -B tools/dump_agent_session.py --dsh ~/.dsh/sessions/--D-Geant4-G4UniversalSim--/<session-id>/session.v4.jsonl.zstd \
    --unzstd /d/msys64/ucrt64/bin/zstd --title "DSH 会话摘要" --out out/collab/dsh-digest.md

# 反向：导出 Codex 会话摘要
python -B tools/dump_agent_session.py --codex ~/.codex/sessions/2026/10/28/rollout-*.jsonl \
    --title "Codex 会话摘要" --out out/collab/codex-digest.md
```

`out/collab/` 被 `/out/` 规则忽略，是临时交换区，不提交；需要长期留存的结论写进 `docs/collab/`。

## 交接节奏

- 每个阶段收尾：DeepSeek 更新 `ASTRA-BRIEF.md` 的“当前状态”段，并在 `outbox/` 写本次交付与待审清单；
  Astra 在 `reviews/` 写结论（含 file:line 与判定强度：确定为缺陷 / 需实验 / 无问题）。
- 结论冲突时以仓库中的实现与测试报告为准，不以任何一方的记忆为准。
