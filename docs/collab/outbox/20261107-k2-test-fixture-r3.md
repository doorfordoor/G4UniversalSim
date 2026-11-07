# K2-2 r3 交付：测试夹具宿主依赖修正

- 时间：`2026-11-07T09:54:30Z`
- 基线：`41991fc64d2bd1a15e8998c2d19a50f85d9a745f`（`roadmap/Q2-scientific-baselines`），模板身份 `b91e34e42b532d605f7ba92178a3ee04d90b30b12c244b496cb7d48cd5a86c81`
- 回执：`out/collab/20261107-k2-implementation/author-r3/receipt.json`
- 范围：只改 `scripts/test_k2_project_export.py` 的夹具与回执；产品源码、模板 manifest、K1、导出器均未动。

## 1. 被证实的宿主依赖

- r2 观测：干净源码归档没有未跟踪的 `tools/collab/`，旧夹具却断言它必须存在（`AssertionError: local collaboration files must stay`）；同一块还要求仓库里预先有 CRLF `.hh`，全 LF 检出会得到 `crlf_member=None`。
- r3 观测：旧 R9 目标放在被忽略的 `ROOT/out/`，归档没有该目录，实际先触发 R2 `destination_parent_missing` 而非 R9。
- 证据（未改动）：`independent/r2-native-linux-static-probe.log`、`independent/r3-native-linux-static-probe.log`。

## 2. 最小修正

- 测试开始时记录本地协作目录是否存在；存在才校验保留，不存在则断言测试没有创建它（不建真实 `ROOT/tools/collab`）。
- CRLF/LF 场景改在本次私有 portable fixture 中主动生成：选定 header 写 CRLF、选定 `.cc` 写 LF，其余成员原样复制；再与仓库实际模板身份、`packaging/export_template_manifest.json` 身份三方相等。
- 私有 `portable/tools/collab/local_helper.py` 夹具证明嵌套协作脚本被排除且不进闭包。
- R9 目标改为 `ROOT/config/k2-r9-target`（模板本来必有的目录）；不为通过而给真实 ROOT 造 `out/`。

## 3. 验证（同一脚本在两种源状态均通过）

- D 当前源：exit 0，`k2 export checks: files=317 identity=05d91b95c66a1c2d template=b91e34e42b532d60 symlinks=yes junctions=yes`。
- 私有干净快照（`git archive 41991fc64d2bd1a15e8998c2d19a50f85d9a745f`，无 `tools/collab`，模板成员全 LF 观测）：exit 0，`k2 export checks: files=317 identity=05d91b95c66a1c2d template=b91e34e42b532d60 symlinks=yes junctions=yes`。
- 两边模板 `--check` 均为 ok；模板身份仍 `b91e34e4…`（308 成员，manifest SHA-256 `ee9e1c88…`）。
- 产品三个源文件 SHA 与 r2 交付完全相同（本轮只改测试脚本）。
- 原 S-A/P3/R1–R12 断言在新夹具下继续执行并通过（同一脚本输出 files=317 identity=05d91b95…）。

## 4. 保留与未执行

- 主审 Windows 两方法失败原样保留，不重试；Linux GUI 子用例按其报告 1 pass/0 fail/0 skip、33 断言、严格证据门通过，本项未重跑。
- 未重跑完整 static/gui profile 与云 CI；未做安装包/安装器/K2-3；未提交、未推送。
- 私有快照为本机 `D:/Temp/k2-r3-clean/tree`（HEAD 归档 + 本轮测试文件），不等于主审 Linux 复跑。

## 5. 结论

两处（含追加 R9 一处）已证实宿主依赖均有界修正：同一脚本在开发工作区和不含本地协作目录、模板成员全 LF 的私有源码归档中都通过，且模板/产品身份不变。等待主审在干净归档复跑后回原 K2-3。
