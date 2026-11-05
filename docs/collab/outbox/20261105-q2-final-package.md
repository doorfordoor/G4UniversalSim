# Q2-6 科研基准交付收尾回执（2026-11-05，初审修正 r1）
Task `q2-final-package`（inbox `20261105-q2-final-package.md`，用户 m18563 初审修正）。只改入口文档与 manifest；无新输运、无云任务、无产品/原始数据/旧失败记录改动，未提交 Git。
- `docs/Q2科研基准与适用范围.md`（136 行）修正：Dose 逐事件估计量改为 `D_e=Σ w·edep[J]/m_kg`（`DoseScorer.cc:71,89-105`；raw 取 w=1），并明确 CSV 存 run 累计量、`mean_per_event` 才除 N；Fluence/DDD 同样写明累计量与每事件归一化；LET_t/LET_d 比值不再除 N；`CSS`→`CSV`；LET v2 冻结合同改为完整 `docs/collab/decisions/…` 路径。
- `scenarios/benchmarks/README.md` 与 `docs/中文使用手册.md` §9 的 Q2 入口小节保留不变（未覆盖 ROOT 现有段）。
- `docs/verification/q2-final-20261105/manifest.json`（10619 B，`c772b3359a9c873e…`）：入口 SHA 已同步；新增 `existing_cloud_records`——产品提交 `864bc036…` 的 Linux/M0/desktop/installation run `41820515533`/`41820515013`/`41820515045`/`41820515620`（`docs/verification/f2-final-20261104/ci-runs-final.json`）；docs-only `f7793dcb…` 的 `41860688390`/`41860689162`/`41860688420`（`docs/verification/e4-final-20261105/ci-accepted-runs.json`）。
- §6 改为“入口核对 + 既有云门禁按原 commit/run id 复用”，不再提议本机 `--profile all` 或四工作流全量重跑；主审最终选定必要批次，文档提交如需云端状态仅触发现工作流一次；不新增框架/统计病例/物理重跑，也不作为 Q2-6 新前置。
- 实际检查：`check_doc_links.py` → 1452 链接/428 文件/0 断链；新文档仓内路径直接存在性检查 0 缺失；manifest 入口 SHA 与产品 exe SHA 复核一致；`git status` 仅本轮 2 改 3 增，ROADMAP/CURRENT/STATUS 与产品/测试/冻结/证据字节未改。
- 限制未变：LET v1 失败、DDD/NIEL limited、Q2-5 原 factor10 失败、Q2-5 r2 单病例、Q2-4 有限样本；全部科学结果仅 Windows/Geant4 11.3.2，不能冒充 Linux/11.4。
- 完成后停止写入，等待独立复审。
