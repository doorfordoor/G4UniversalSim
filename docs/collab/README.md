# 跨代理协作信箱（Codex/Astra ↔ DSH/DeepSeek）

本目录是**两个代理之间的文件信箱**。谁在第几轮说了什么不靠粘贴，靠这里的文件和仓库本身。
阶段状态仍只由 [ROADMAP.md](../ROADMAP.md) 维护，功能支持等级仍只看 [功能支持矩阵](../功能支持矩阵.md)；
本目录不改变任何验收标准，只记录交接内容。

## 角色（2026-10-28 用户确认）

| 代理 | 位置 | 职责 |
| --- | --- | --- |
| Astra | Codex（总设计师） | 架构/协议设计、复杂诊断、科学方法审查、验收标准、关键决策 |
| DeepSeek | 本仓库的 DSH 会话 | 前端（GUI 交互/视觉/信息架构）设计负责人、实现、本机真实验证、证据工业化 |
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

两个代理共用同一个工作区，同一时刻只能有一个写者：

1. 默认 DeepSeek 是写者（提交、推送、跑测试）。
2. Astra 要做只读审查时，不需要交接，直接读工作区即可；如果 Astra 需要改代码，先在
   `docs/collab/inbox/` 写一份改动提案（含文件清单与验收标准），由 DeepSeek 实现并回报，
   避免两边同时改同一文件。
3. 任何一方开始写之前，先 `git status --porcelain`；不为空的非自己改动一律不碰、不覆盖。

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
