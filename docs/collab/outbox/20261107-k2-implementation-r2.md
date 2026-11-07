# K2-2 r2 交付：干净检出模板身份修复

- 时间：`2026-11-07T09:22:30Z`
- 基线：`d999e2366460ba75503c67a2dd6a0c35e7eb5a55`（`roadmap/Q2-scientific-baselines`），修复依据 `docs/collab/decisions/20261107-k2-clean-checkout-template-fix.md`
- 回执：`out/collab/20261107-k2-implementation/author-r2/receipt.json`

## 1. 失败原因（r1 复验）

- 模板成员枚举把本地未跟踪的 `tools/collab/` 两个脚本当作模板成员，而评审的干净检出没有它们。
- 另外 9 个成员在检出时是 CRLF、开发树为 LF，指纹按字节计算即失败。
- 证据：`out/collab/20261107-k2-implementation/independent/clean-checkout-template-failure.json`

## 2. 修复（最小范围）

- 模板闭包统一按规范字节（CRLF/CR → LF，字节幂等）计算 `sha256`/`bytes`/`identity`，并复制规范字节；checkout、安装模板与打包生成器共用同一算法。
- `tools/` 只取顶层直接成员；`tools/collab/` 保留在本地但不进清单、不进 Git、不随导出携带。
- 模板清单已重生成；`verify_export` 仍按导出树真实原始字节校验，不规范化。

## 3. 身份

- 模板：`b91e34e42b532d605f7ba92178a3ee04d90b30b12c244b496cb7d48cd5a86c81`（308 成员，3,816,681 B；manifest SHA-256 `ee9e1c88853a8d82b69717c40c6cad14afab75820ccc08b408e4b521c4222ca7`）
- r1 的 `2c4f39c3…`（310 成员）作为历史失败保留，不再是候选身份。
- 导出 payload：`05d91b95c66a1c2dbe3b486e86e731ed93391d28dc9f6e7f7fdde8e1b27274c6`（317 文件），checkout / 干净检出模拟 / 安装模板三种来源一致。

## 4. 已执行自测

- 专注套件：`k2 export checks: files=317 identity=05d91b95c66a1c2d template=b91e34e42b532d60 symlinks=yes junctions=yes`（P1–P9、R1–R12）。
- 干净检出模拟：`git archive HEAD` + r2 六个工作区文件覆盖，模板 `--check` ok、与开发检出/安装模板身份一致；三来源 S-A 导出 payload 相同；导出模板字节为规范 LF；CRLF 篡改被 `verify_export` 拒绝。
- GUI smoke：`ok`（`gui_export_project`）。
- 文档链接：1505 relative links in 523 files, 0 broken。
- 规则文件 `tools/collab/` 仍在本机、未进模板，示例项目字节未变。

## 5. 未执行 / 限制

- 评审者 C 工作区的实际复跑由主审执行；本回执以 HEAD + 本六文件覆盖的干净树模拟，不等同主审复跑。
- 未重跑完整 static/gui profile（r1 的未跟踪文件 gate 与缺少编译组件 PATH 前置导致的失败仍保留在 r1 证据中，未被重分类）。
- 未做完整安装包构建、安装器构建、云 CI、K2-3；未提交、未推送。
- 模板规范化只覆盖模板闭包；项目输入/README/导出输出仍按真实字节核验。正式矩阵仍为 not_passed。

## 6. 结论

破坏性根因已闭合：同一稳定候选在开发检出、模拟干净检出与安装模板布局得到同一成员集合和同一 digest；
本地 `tools/collab` 保留且不进入可携带身份。等待主审独立复验；K2-3 待本交付冻结后启动。
