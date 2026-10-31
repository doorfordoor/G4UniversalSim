# K1 P1：r3 晚变化资源路径独立 Windows 补验

结论：当前 r3 在本次独立可控 NTFS fixture 中正确拒绝晚变化目录 junction，且保留普通外部资源 SHA 复核；真实 8.3 别名的生成包导出和离线搬移仍成功。原 r2 反例可重现。此结论只支持本 P1 缺口裁决，不签署整个 K1 阶段。

验证时间：2026-10-31 12:29:36–12:29:45 UTC。工作区 HEAD `e93072867021ae1978a7de3834c51caf0f9fb839`，前后 git status --short 均为空。产品/正式测试/旧证据均未修改。适配器、收据和 fixture 全部在本专属证据根。

实际载入身份：

- r3 `gui/g4usim_gui/core/experiment_bundle.py`：`5c1dff0338e80a673ba8f3427aeb7bfe1abe9d2b5315efca564310be8118385a`。
- 旧 r2 从原归档只读载入：`34db09d96260841411dc92306f4eab438d75792a4f74abacde3322c10b3d66c2`。
- 解释器：`D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe`。每个命令与实际模块路径/SHA、原始落盘日志 SHA 均在 `validation-receipt.json` 和逐 case 收据。

| 独立 case | 实际行为 | 退出码 | v3 入口 |
| --- | --- | ---: | ---: |
| old-r2-junction | 收据捕获后把本任务 external-source 换为指向 staging/resources 的真实 NTFS junction，r2 错误发布；重现旧缺陷 | 0 | 21 |
| current-r3-junction | 同一语义 fixture，`Bundle refuses reparse point`，无发布目录，暂存目录已清除 | 0 | 21 |
| current-r3-content-change | 捕获后普通 materials.ini 字节变化，`Resource changed before publication`，无发布/暂存残留 | 0 | 14 |
| current-r3-real-alias-relocation | 原 Windows-only fixture 原字节执行，真实 samefile 8.3 别名导出；复制后隐藏原输入/原导出，inspect/load 仍成功 | 0 | 15 |

合计 71 个 v3 适配器 assert 入口，属于保守执行入口计数，不是 71 个独立物理事实。别名 case 还执行了归档 fixture 的原有断言，但其源文件不在外层适配器探针跟踪范围，不把这些断言额外计入 71。最长实际 writer main.ini 为 318 UTF-16 单元；搬移副本 10 个文件逐 SHA 一致。所有 case 没有启动 Geant4 后端，没有原生 GUI 观察或新增物理验证。

旧探针两个 exit0 的含义已核对：base 断言拒绝，candidate/r2 断言错误发布，故不能拿旧 exit0 当作 r2 边界通过。新 r3 case 明确断言应拒绝，并同时要求不发布、无暂存残留、源字节前后相等、临时 junction 已删除、原 source 目录恢复。操作边界先核绝对路径包含本 case 根；只删除自建 junction 本身，不递归删除用户目录。

## 给 root / k1_p1_resumed_review 的正式回归缺口

现有正式 `scripts/test_k1_staging_alias.py` 的对应分支是静态 link/junction 目标拒绝，并明确注释为 “not an in-flight mutation”。它没有在 `inspect_bundle(staging)` 成功后、publication 前改变 external receipt 路径，因此**尚未永久覆盖这次已确认的晚变化拒绝语义**。现有等价目录拼写和静态链接断言不能替代这个反例。

建议在现有同一正式用例中补一个最小 case，不另增测试数量：使用独占新子目录的 external fixture，保存原源字节；包装真实 inspect 调用，在首次 staging 完整核验返回后将 owned external-source 目录改名、建立指向 owned staging/resources 的目录链接；真实 export 必须报 linked/reparse 拒绝、目标不存在、暂存消失；finally 只去除自建链接、恢复目录，并断言源 SHA 不变。Windows 用真实 NTFS junction（无须开启 symlink privilege），Linux 用普通目录 symlink；Windows/双 Linux 仅补跑受影响正式用例及证据门禁，再由 root 明确其测试身份与已有冻结矩阵的映射。普通内容变化 case 可沿用既有源变化测试，不必为数量扩充。未经 root 裁决，本写者没有修改正式脚本或产品。

本次未重跑 Linux：独立补验的直接缺口是 Windows NTFS/8.3 行为，已有矩阵由主任务核验。若永久测试发生变化，应执行上段的跨平台专项，不能以本 Windows 补验冒充新增 Linux 覆盖。

## 文件

- `validation-receipt.json`：命令、退出、入口数、实际落盘日志 SHA、保护文件前后 SHA、HEAD/status。
- `late-r2-junction/receipt.json`、`late-r3-junction/receipt.json`、`late-r3-content/receipt.json`：实际载入产品身份、错误、发布状态、源前后 SHA、变化观察。
- `real-alias-relocation/receipt.json` 和 `relocation-receipt.json`：真实别名、writer 实际长度、零 missing read、搬移文件 SHA 与原路径不可用时加载。
- 四份 `*.log`：未删改原始 stdout/stderr 字节。
- `late_boundary.py`、`alias_relocate.py`、`run_validation.py`：本次专属适配器。每个 case 独占创建目录，整套 runner 不应在原 case 目录上重跑覆盖证据。

当前下一动作：root 裁决永久回归最小补充，再由独立审查结合上述原始证据判断 P1 是否可关闭；整 K1 另按阶段证据验收。
