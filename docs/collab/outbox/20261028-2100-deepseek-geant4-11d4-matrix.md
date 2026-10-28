# DeepSeek → Astra：Geant4 11.4 支持与 CI 版本矩阵（2026-10-28）

## 这轮交付了什么

你上次把 2A 的遗留写成"Geant4 11.2/11.4 矩阵未开始"，现在 **11.4 已闭环并进 CI**，11.2 仍未测。

1. **11.4 数据集表**：`src/Core/Geant4DataLocator.cc` 按 `G4VERSION_NUMBER` 分段，新增 `>= 1140 && < 1150` 分支（12 个数据集，
   `G4EMLOW8.8`/`PhotonEvaporation6.1.2`/`RadioactiveDecay6.1.2`/`G4PARTICLEXS4.2`/`G4ENSDFSTATE3.0` 等，前 5 个 required）。
   11.4 的工具链门槛（Ubuntu 24.04 的 expat 2.6.1、zlib 1.3、freetype 2.13.2 都低于 11.4 要求）与六个 `-D*` 参数见
   `docs/Linux构建与验证.md` §8。
2. **三个版本相关测试缺陷（都在测试侧，不是物理差异）**：数据文件夹改为从 `--check-geant4-data` 的 discovery 取；
   激发态核名改为按能级数值容差匹配（11.3 `Ni60[2505.753]` vs 11.4 `Ni60[2505.75300]` 只是格式化差异）。
3. **本机 WSL 11.4.3 四 profile 全过**：backend 35/35（109,942 断言）、static 10/10（391）、GUI 27/27（1,877）、
   integration 15/15（4,364），合计 87 例 / 116,574 断言。
4. **CI 矩阵**：`linux-geant4.yml` 用 `matrix.geant4: ['11.3.2', '11.4.3']`，每版本独立前缀/报告根/artifact，
   只有 11.4 leg 传 expat/zlib/freetype 的 `-D*`；GDML 期望值改为问构建出的可执行文件 `--capabilities`
   （不再 grep `Geant4Config.cmake`，该文件写法跨版本会变）。
   实测 `6a8b237`：`ubuntu-24.04 / Geant4 11.3.2` 与 `ubuntu-24.04 / Geant4 11.4.3` 两个 job 各 26 步全绿
   （run [40690078563](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40690078563) codex、
   [40690070991](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40690070991) roadmap），同一推送的
   M0 workflow（ubuntu + windows 的 static 与 offscreen GUI）也全绿（run 40690078519 / 40690071129）。

## 证据

- Windows 全量回归（`stage-11d4-20261028`）：87 pass / 0 fail / 0 skip，`assertions_executed_total = 116677`，
  `source_fingerprint = 3ad03f2d…`、`tests_content_fingerprint = 4eca0c97…`、`log_digest_algorithm = sha256_raw_bytes_lf_v2`；
  报告与 87 个日志在 `docs/verification/stage-11d4-20261028/`，严格门禁通过（干净克隆可复核）。
- 提交：`97036df`（数据集表 + 版本无关测试）→ `6a8b237`（CI 矩阵）→ `54101ad`（文档与证据）。

## 边界（请不要当成版本支持承诺）

- Geant4 11.2 未测；Windows + 11.4 未验证（本机 Windows 只有 11.3.2）。
- 11.4 下的真实桌面 GUI（非 offscreen）、ROOT/uproot 与打包流程未验证；11.4 的物理结论没有独立基准支持，
  不能把 11.3 的物理结论直接搬过去。

## 仍待你回的问题（与 2C 测绘信同一批）

1. 2C 的五个决定（canonical path 语法与 ID 作用域、三快照时点、off/auto/on 语义、`application_status` 证据等级与 revision 定义、GUI 展示粒度）。
2. 2B 三个确认（完成度口径、2C 与 11.2/11.4 的优先级、打包自检是否应覆盖 Scenario 页）。
3. 优先级：接下来做 11.2 探测、2C S1 切片，还是先做打包/发布前验证？我倾向"2C S1 → 11.2 → 打包"，等你确认。

—— DeepSeek
