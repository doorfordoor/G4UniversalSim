# H3-1 合同首轮独审（2026-11-06）

结论：失败，尚不冻结/不授权产品实施。草案原件 out/collab/desktop-bridge/h3-contract-r1.md 保留。当前源码83c0b139，固定清单不扩大。

1. **计分路由会污染旧结果（阻断）**：src/Scoring/ScoringManager.cc:685-720 的 ScoreHit 先累加 currentEventRawEdep/currentEventWeightedEdep，再 WriteHit，再广播所有 enabled scorers。草案“不改ScoreHit自动路由且不写hits”不成立。最小方案增加专用并行体积计分入口，只调用明确的体积scorer，不进入质量世界event/hits/默认能谱等累积。零沉积Fluence保持一次计分。合同须列实际调用链与不重复计数反例。
2. **worker生命周期事实错误（阻断）**：Geant4 v11.3.2 G4WorkerRunManager.cc:151-153明确调用ConstructSDandField与ConstructParallelSD。见 https://raw.githubusercontent.com/Geant4/geant4/v11.3.2/source/run/src/G4WorkerRunManager.cc 。几何共享与worker SD/TLS须分开，ConstructSD不能写共享sd指针；threads=1也可能是MT单worker。固定清单要求线程生命周期与合并，不能以错误的master-only前提永久缩为单线程。Case M成功退出应为0；每worker输出字节相等不是无竞争证明，调度分配可能改变。应核对完整事件N、独立SD/累积、聚合结果及连续run隔离，按实际支持线程模型执行。
3. **原范围网格接口缺失**：Roadmap/清单明确meshes与计分体积。草案只支持手写16个box并拒绝全部mesh，不足以宣称网格完成。提供规则网格明确配置、索引、边界、归一化与真实消费者，或说明如何复用现有mesh。无需任意形状/新框架，但不得通过拒绝清单删掉原需求。
4. **包含与Case C输入无效**：100mm全长world范围±50mm，中心z=50mm、边长1mm的box越界，且位于束流轴线上，不能称远在束流外。改为明确在实际质量world内部、离轴的真空探针（例如30,30,0mm），描述仅初级束不直穿，不承诺次级绝不命中。声明world.size不用于构造，不能代替实际ghost world包含验证；统一全长/半长单位。
5. **统计签收不充分**：Case B/C以点估计偏差和半宽分别≤阈值仍可让99%区间伸出等效界限（例如偏差0.9%、半宽0.9%）。冻结采用整个Welch 99%差值区间落入预定等效界限，给明确标准化分母。精度不足=inconclusive，偏差超限=失败/调查，不自动标limited并声明不是产品缺陷。与原核心要求冲突的限制不能预授权带限关闭。固定种子/批次保留，不加数据追通过。
6. **归一化名称**：layeredMass=false下沉积来自质量材料，ghost声明材料仅用于参考质量。若与实际材料不一致，不可称任意材料真实吸收剂量；明确参考归一化与匹配材料病例的真实含义。保留正确的weight一次、事件N定义。Geant4过程见 https://raw.githubusercontent.com/Geant4/geant4/v11.3.2/source/processes/scoring/src/G4ParallelWorldProcess.cc 。
7. **契约内部矛盾**：enabled=false既称旧行为又一律拒绝，须统一（显式false且无活动配置可禁用，附带活动配置如何诊断须定稿）。配置期不可能在创建任何G4对象前完成实际G4Material密度核对，分结构预检与内核对象就绪后/事件前验证。默认回归比较科学输出及字段语义，不能要求身份SHA/时间路径相同。
8. **基准可执行性**：列准确四个端点及CSV列名（raw_track_length_mm、weighted_track_length_mm），区间和按各加数舍入误差累加，不拿总和单个半单位代替。Case A2粒子在网格交界，应明示边界所有权。A2f质量hits独立复算须先证明专用路由不写平行行。ROOT/field等组合拒绝给真实依据和影响，不凭“不可解释”泛化。修复后仍只执行原固定清单。

修订只改原合同与其回执；当前不写产品/测试，不跑正式基准。交付后主审再次核验上述阻断点。
