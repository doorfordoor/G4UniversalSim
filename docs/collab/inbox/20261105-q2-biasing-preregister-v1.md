# Q2-5 XS 偏置与 analog 对照预注册

任务 ID：q2-biasing-preregister-v1-20261105。提交一套可冻结的单病例实验合同、精确输入和无输运自测。冻结前不运行任何该病例、试种或读取同一预定病例结果；不另造验证框架。

- 从 Q2 固定清单和 [原偏置草案预审](../reviews/20261105-q2-biasing-preregister-review.md) 出发。使用已回归的 `scripts/test_biasing_step_weight.py` 物理/几何路径：10 MeV e−、G4_Pb 10 mm 立方单敏感体、G4_Galactic 世界、中心点源 +z、FTFP_BERT、cut 0.1 mm，偏置 eBrem/Target。去掉额外 gamma 源和 mesh，仅留下这一个初级粒子及主量所需评分。固定 factor、only_primary、apply_to_secondaries、min_weight、max_interactions，明确为何能观测到非单位权重。analog 是实际不注册偏置，不用 factor=1 替代。两组除偏置门控和规定独立种子外，几何、源、原始物理截面和评分完全相同。
- 主终点是每个完成事件的加权沉积剂量（Gy/event，单敏感体）。写清完整 event_edep、实际质量、实际 worker 绑定/调用及正有限权重的独立检验，零事件行保留。对账 event_edep、Dose 汇总与统计 S/S²/R；hits 仅用于已输出的沉积步和权重观测，不当作路径或事件全集。核对真实 `[G4USimBiasing]` worker 回执，不能以配置已接受或 `biasing_effect_observed=unknown` 作权重实证。
- 默认方案为两组各 16 个独立批次，每批 2,000 事件、2 线程，32 个新且不重叠的种子，运行顺序固定并平衡两组先后。用可复现的事前物理/资源依据确定最终规模；若调整默认值，附依据。预注册后固定，不中途换种、扩样或丢掉异常批次。
- 给出一个明确的组间主比较和区间构造，例如对等 N 的批次均值作独立两组 Welch 99% 区间，写明有限样本和非正态近似限制。避免将运行顺序分组当成共享随机数的配对设计。给出纯数学正反例、错误判据和无穷/零方差处理。区间含零只表示在该分辨率下兼容，不证明等价或全局无偏；统计异常不直接归因后端，保存原始证据。列出组内批次不确定度和事件估计量，不能当作彼此独立的重复显著性试验。
- 效率比较使用真实 `scorer_statistics.csv.run_wall_time_s` 及可复算的 FOM=1/(R²T)，主机墙钟另列，不伪造缺失值。单机/两线程、串行启动、同等事件预算，报告时间和方差；没有收益是有效结果。预先定义缺文件、无事件、零总量、权重和绑定证据缺失、过程错误及超时的失败或限制，不用剩余批次静默替代。
- 仅写 `out/collab/q2-biasing-proposal-v1/**`、`docs/collab/outbox/20261105-q2-biasing-preregister-v1.md`。提交草案 JSON、精确 INI/macro、种子/顺序清单、原始字段/出处、源与输入 SHA、纯数学核验及负对照，注明复演命令。初次交付后停写等独审。状态必须是 draft、execution_authorized=false；不更改 Q2-4、产品、正式测试或阶段文件，不提交 Git。

你是本轮执行负责人，请有信心把这个高级科研项目做完整、清晰、美观、快速、易用。unlimited Token，不限子智能体数量，充分发挥设计和工程能力，充分实现与验证。实际平台限制以系统为准，不为消耗而重复工作。完成约定范围，范围外想法记入建议。
