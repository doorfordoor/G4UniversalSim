# Q2-5 带电电子 XS 偏置修复基准 r2 回执

Task: `q2-biasing-repair-r2-20261105`（用户 m18225）。结果：本病例候选基准
（`factor = 1.2` + 靶内 `max_step = 0.01 mm`）已完成并通过固定门禁。

- 身份：plan `a345fc8a58f4a607…`（7032 B，`g4usim_q2_biasing_repair_r2_plan_v1`）；
  identity `ca69e84be04f9b44…`；seed-order `8a6a58f7331e7732…`；上游
  biasing-freeze-r1 `d2e3837d5202616f2a2f6dc2d2269286ec68eb447464c0826cf23e2953c6c6e7`、
  proposal `a7f590fd85a56749af1487207c6cbc238a9b6d4b04fb2d28ba5e6e31d4f54d9a`；
  backend build `864bc036…` / exe `f8a8119d…` / Geant4 11.3.2；4 个输入按 r2 计划冻结；其中 geometry/run.mac 与 r1 逐字节相同，两个 main INI 已修订（geometry `11a04452…`、main_analog `4a8d3359…`、main_biased `11a79313…`、run.mac `3e03251e…`）。
- 实际运行：32 次后端启动（16 analog + 16 biased，每批 2000 事件 / 2 线程），
  32 条记录全部 exit=0、completed、64000 事件；未重跑/补批/换种/覆盖，无第 33 次启动。
- 原始数据：原 factor 10 执行 `out/collab/q2-biasing-execution-v1/` 字节未改；
  根因证据 `out/collab/q2-root-investigation/`；本 r2 输出在 `runs/`，副本反例在 `tampered/`。
- 结果：analog `1.0806620583713778e-10`、biased `1.0793015488236168e-10` Gy/event；
  Welch 99% delta `-1.360509547760978e-13`，CI `[-8.496103105526374e-13, 5.775084010004418e-13]`，
  decision `compatible`；相对半宽 0.6603 %（上限 5 %）。`compare.py` 428/428 pass。
- 时间/效率（中位）：wall 9.9440 / 9.8057 s，host 12.4015 / 12.2570 s，FOM 3054.84 / 1337.91 s⁻¹；
  biased 无效率收益，如实记录。
- 改动：新增 `out/collab/q2-biasing-repair-r2/`（README、plan、identity、seed-order、
  inputs、results `905d2ea3aba361d6…`、evaluation `aeb48cd8550cf257…`、
  tamper-results `cbeb544f642cd1c3…`、脚本、runs、tampered）；
  `docs/中文使用手册.md` §10 增加 11 行带电偏置警告（全文 `aaf1360c62924b95…`）。
- 门禁：tamper 7/7 真实 fail、原件 114 文件哈希不变（6 端点反例只重算目标批，
  CE-DROP-BATCH 复用 31 批已验证结果）；doc_links 1448/423/0；产品/测试/冻结/原 32 批零改动；
  未提交 Git。冻结证据目录只读复核；输运复演须在独立新目录进行。
- 边界：只覆盖本病例；`factor = 10` 原失败未修复、不回填；`0.01 mm` 非通用保证；
  “兼容”不证明全局无偏。详细证据与复演说明见 `out/collab/q2-biasing-repair-r2/README.md`。

主审文字勘误：原回执误写四输入均与r1相同，现按实际SHA更正；原回执保留在候选目录 author-receipt-original.md，未修改运行原件。
