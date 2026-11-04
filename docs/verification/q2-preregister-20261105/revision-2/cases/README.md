# Q2-1 参考包 · 病例索引

本目录是 Q2-1 科学基线预注册的病例草案，**未运行模拟**，只冻结判据与输入。
A 组（本文件索引）见 [`implementation-cases.md`](implementation-cases.md)：用
“几何/材料配置 + 原始逐事件输出 + 输入表/权重文件”独立重算，专门抓质量、体积、
权重因子的重复相乘；每例的第 5 节是权重测试（`weight=1` vs `weight=2` 的相空间对）。

| ID | 一句话目的 |
| --- | --- |
| **IMP-DOSE-01** | 用 `m_geom=ρ·10×10×2 mm³` 独立核对 `mass_kg`，并用 `ΣE/m` 抓质量重复乘；10 MeV 质子全部停在靶内，`ΣE=N·E`。 |
| **IMP-FLU-01** | 用 `V_geom=10×10×0.1 mm³` 与 `ΣstepLength/V` 抓体积重复除；12×12 束打 10×10 靶的解析注量 `Φ=N/144 mm⁻²` 作统计判据。 |
| **IMP-LET-01** | 用 `let_t=ΣwSl/Σwl`、`let_d=ΣwS2l/ΣwSl` 抓分子/分母错配与步集合；权重 ×2 时三个线性 sum ×2、平方/交叉和 ×4、比值不变。 |
| **IMP-DDD-01** | 用常量 NIEL 表（0.003 MeV·cm²/g）把 `DDD=100·L·NIEL/V` 变成纯算术，抓体积重复除与漏乘 100；实表折积只作 1% 量级检查。 |

共同约定（模板、列名、容差、G/R/I 三条证据链、统计矩一致性、相空间权重写法）见
`implementation-cases.md` 的 §0；`待验证` 键与功能缺口见各例 §8 和 §10。

同目录的 B/C/D 组（外部物理参考、不确定度、偏置）分别见
[`reference-cases.md`](reference-cases.md)、[`uncertainty-cases.md`](uncertainty-cases.md)、
[`biasing-cases.md`](biasing-cases.md)；A 组不重复它们的外部参考判据。
