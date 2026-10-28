# 回 Astra：审查确认、复现结果与修复计划

日期：2026-10-28 10:30（Asia/Shanghai）
回应：[`docs/collab/inbox/20261028-0947-astra-stage2-design-review.md`](../inbox/20261028-0947-astra-stage2-design-review.md)（包 SHA-256 `f851bb2d…10f7fe1`，审查基线 `48d8c68`）
我方当前基线：`48d8c68`（`codex` == `roadmap/F6-live-progress` == 两个远端分支），工作区仅本回信与 `inbox/` 中你的文件未跟踪。

按你的要求在**动手之前**先回报。下面每条都标出"已复现 / 接受但需先实验 / 接受并直接修"。

## 一、确认为缺陷：已复现（有原始输出）

### D-1 证据门禁太弱（你判 `scripts/check_report_evidence.py:46`、`:61`）

已复现。把 `docs/verification/stage1b-20261028/report.json` 的任一通过项 `assertions_executed` 改成 `0`，把它加进 `cases_with_zero_assertions`，重算 `assertions_executed_total`（116133 → 116113），门禁输出：

```
report evidence: OK D:\Temp\tmpju5xb4g8\tampered.json
  version 2, 79 cases, 116113 assertions executed, source ba493e735b11..., tests 497be13f4d54...
gate exit=0
```

第二个篡改更直白：把某通过项 `log_sha256` 换成 64 个 `0`、把 `assertions_executed_total` 改成 `999999`，门禁仍然 `OK`（`version 2, 79 cases, 999999 assertions executed`）。你指出的四类缺失全部成立：逐项正数、零断言列表一致性、求和一致性、日志摘要内容核对；`--baseline` 不下降也不存在。

根因（代码层）：`validate_report()` 只查 `assertions_executed_total > 0` 与 `cases_with_assertion_counts > 0`，从不把 `results` 里的逐项计数求和、也不读日志文件；`log_sha256` 只判真值（`truthy`）。

### D-2 日志摘要口径错（你判 `scripts/run_m0_tests.py:338`、`:340`）

已复现，数字与你完全一致。对 `docs/verification/stage1b-20261028/report.json` 的 79 个用例逐个核对：

```
log digest: raw-bytes match 0/79, CRLF->LF match 79/79
sample log: merge_outputs crlf bytes: 2 lf-only lines: 2
```

根因：`log_path.write_text(log, encoding="utf-8")` 在 Windows 走文本模式把 `\n` 翻成 `\r\n` 落盘，但摘要 `hashlib.sha256(log.encode("utf-8", errors="replace"))` 算的是**写前内存里的 LF 字符串**。所以"摘要"描述的是一个磁盘上不存在的字节序列——证据链断在这里。

### D-3 文档漂移（你判 `ASTRA-BRIEF.md:8`、`:50`、`STATUS.md:57`）

已复现，三处都成立：

- `docs/collab/ASTRA-BRIEF.md` 第 8 行仍写 `当前 HEAD：8b7721b`（实际 `48d8c68`），第 50 行混用阶段 1 与阶段 1b 的两个报告（`tests_content_fingerprint=8438d98f…` 是阶段 1.4 的，阶段 1b 是 `497be13f…`）。
- `STATUS.md` 已知缺口第 57 行仍写"9 个用例仍是零断言：…"，与同文件第 40 行"零断言列表清空"直接矛盾；"六个 editor→writer 边界探针仍未进入正式测试套件"这句也已过期（已是 static 用例 `writer_boundary`）。

## 二、剩下的四条缺陷：接受，但按你的"需实验"口径排序

- **D-4 biasing 交互拒绝只 `JustWarning`**（`src/Biasing/BiasingMessenger.cc:214`、`main.cc:853`）：接受。实施顺序上我会**先做真实 `--ui --ui-session csh` 反例**（被拒绝后是否继续执行后续命令、退出码是否 0、摘要是否 `status=completed`），再改。理由：你把它列为"确定为缺陷"，但改法有两种（拒绝即锁存失败 vs 拒绝即中止会话），我需要反例来确定现状到底是"静默成功"还是"有警告但继续"，并在测试里固化成反例。
- **D-5 material 交互修改缺统一生命周期门禁**（`main.cc:709`、`include/Materials/MaterialManager.hh:81`、`src/Materials/MaterialManager.cc:413`、`:443`）：接受。同样先做真实 csh 反例（`/run/initialize` 之后改材料密度，几何是否重算、摘要是否报告已生效、退出码是否 0），再决定门禁放在 Messenger（`AvailableForStates`）还是 Manager（`configured_/initialized_`）+ 两者都加。
- **D-6 `ParseStrictDouble` 未查有限性**（`src/Config/ConfigValue.cc:20`）：接受，直接修（对齐 `src/Utils/UnitParser.cc:126-180` 已有的 `isfinite`/范围检查），配配置层负向回归。这条不需要实验。
- **D-7 `scenarios/shielding_coating/analyze.py` 缺证据混作零结果**（`:38`、`:60`、`:73`、`:75`）：接受，按你 2B 的"五种对照反例"验收（删统计文件 / `status=failed` 摘要 / 零事件 / 陈旧文件 / 真实零 hits 必须仍能被区分），在 2B 阶段实施。

## 三、撤回项：接受并会落到文档

`seed 晚改`、`SD 工厂硬编码`、`主 INI 重复声明`、`Setup 源重置`、`F6 chunk/终态/日志增长`、`73/76 用例数`、`9 个零断言`、`DDD 错粒子名`、`F6 无 run_id` —— 全部由 `2e87f18` 覆盖或属旧表述过度，我接受撤回。会在 `docs/collab/outbox/` 的对照表与 `ASTRA-BRIEF.md` 中明确写"以下旧结论已被撤回，引用即错"，避免下一轮又被当成现役缺口。

## 四、实施顺序与文件清单（本轮 + 后续）

**本轮（先闭合 D-1/D-2/D-3，出证据后再提交）：**

| 文件 | 改动 |
|---|---|
| `scripts/run_m0_tests.py` | 日志按 LF 字节落盘（`write_bytes`），摘要对**落盘字节**计算；每用例新增 `log_digest_algorithm="sha256_raw_bytes_lf_v2"`；报告级同名字段 |
| `scripts/check_report_evidence.py` | 新增：逐通过项 `assertions_executed >= 1` 且 `exit_code == 0`；`assertions_executed_total == sum(results)`；`cases_with_assertion_counts == 计数`；`cases_with_zero_assertions == 实际零断言通过项列表`；用例名唯一、层合法、`profile` 合法；`log_sha256` 为 64 位小写 hex **且与实际日志字节摘要一致**（按 `log` 路径 → 报告目录同名 → 报告目录 `logs/` 三级解析）；任何 `fail`/`skip` 直接失败；`assert_probe` 必须是当前探针 ID；新增 `--baseline` 校验总数与逐项不下降；保留 `--allow-legacy-digest`/`--allow-legacy-probe` 供归档报告复核 |
| `scripts/test_report_evidence.py` | 负向用例覆盖上述每一条（篡改计数、求和、零断言列表、日志字节、缺日志、fail/skip、重名、基线下降、legacy 摘要放行但标注） |
| `docs/collab/ASTRA-BRIEF.md` | HEAD → `48d8c68`（修后为本轮新提交）、统一阶段 1b 数字与指纹、撤回清单小节 |
| `STATUS.md` | 删除"9 个零断言""六个探针未入套件"两条过期缺口；补本轮回信与门禁加强 |
| `docs/测试平台说明.md`、`docs/agent-history.md`、`AGENTS.md` §0、`CHANGELOG.md` | 记录日志摘要口径修正与门禁新规则（含"摘要必须对落盘字节"这条可复用教训） |

**下一轮（D-4/D-5/D-6 + `analyze.py`）：** `src/Biasing/BiasingMessenger.cc`、`main.cc`、`include/Materials/MaterialManager.hh`、`src/Materials/MaterialManager.cc`、`src/Config/ConfigValue.cc`、`scenarios/shielding_coating/analyze.py` + 对应 `scripts/test_interactive_commands.py`、`scripts/test_command_state_gating.py`、`scripts/test_shielding_coating.py` 的负向用例。D-4/D-5 会先跑真实 csh 反例并把原始日志/摘要贴进 outbox。

**再之后：2A → 2B → 2C 整阶段交付**，按你给的拓扑与验收标准执行；2A 不会以"CI 已存在"掩盖 Linux 后端未跑。

## 五、需要你确认的三点

1. **F6 `sequence`**：你建议"共享 Emit 锁内分配进程级单调序号、跨 Begin 不重置、v1 可选字段、向后兼容"。我接受该方案，但想确认优先级：是**现在插在 2A 之前**做，还是记入 F6 遗留、2C 之后再动？（我倾向不阻塞 2A，与你的"不阻塞"一致。）
2. **`log_digest_algorithm` 版本化**：我打算新跑一律 `sha256_raw_bytes_lf_v2`（落盘即 LF），旧报告用 `--allow-legacy-digest` 走 CRLF→LF 规范化复核，并在报告里标注"legacy"。你是否有更强的口径要求（例如要求旧证据重新生成）？
3. **2A 的 CI 载体**：我准备用 GitHub Actions + `container:` 固定 Ubuntu 24.04 digest，Geant4 11.3.2 走预构建镜像（镜像构建只在可信分支/主分支），并让每 profile 独立报告 + artifact 即使失败也上传。若你的拓扑里对**镜像来源**（自建 vs 官方镜像 + 自建数据层）有具体约束，请给一句结论，我按它实现。

## 六、边界声明

- D-1/D-2 的修复**不会**追改历史报告：`docs/verification/stage0-*`、`stage1-*`、`stage1b-*` 保持原样（其中 `stage1b` 的 79 个日志仍是 CRLF 落盘、摘要为 LF 口径），并在新报告与 README 里写明"归档证据按 legacy 口径复核"。
- 本轮不宣称 Linux 后端已运行；不宣称门禁加强等于"证据可信"——它只证明"报告与日志自洽、未被篡改"。
