# AR3 分析证据与低计数切片：主审限定签收

2026-11-09，当前主审接受本切片的已验证实现与工程生命周期结果。AR3整体、AUD10磁场重放及MR1仍未完成；本报告不作物理精度或统计模型适用性签收。

## 候选和行为

共享analysis_evidence读取同一已验证输出快照，核消费字节、运行完成事实及输入角色。B3缺少必需统计量时返回null/partial而非测得零，失败运行不发布新成功报告；B4在低计数、空窗口、零分母和固定20批不足时保留可计算量并给出不可估状态。原公式和科学门限保持。

独审发现的默认生成谱energy_MeV=null不兼容、零线程被当作一线程已修。null只在匹配的histogram输入下解释，非法类型和冲突仍拒绝。benchmark消费者不将null当有效零，缓存报告对应自身输出目录。

本次代码身份见 `out/collab/20261108-ar0-ar6/ar3-integrated-r2/owned-files.json`；后端source为105b6ab739be8e1897a3cecd4d3d72283e99972ec4ebda783fc199223d6acd9b，实际程序SHA为6f779ef8d5454ffccbe2bddd8db91bb9250be1ae05b60f8af7d2ccc857cf1e5b。当前HEAD d3b5e078不等于工作区内容身份。

## 已核证据

- 作者161个合成例、720断言；Franklin独立39条CLI正反例，并核1865项所列产物SHA。包含真实生成器的三种默认谱格式，但合成统计不冒实际输运。报告：`independent/ar3-scenario-analysis-review-r2/review.md`。
- 主审正式静态/GUI报告 `ar3-integrated-r2-tracked/static/20261109-014246-be8c9a67/report.json` 十项通过、66948断言，严格候选身份门exit0；其中B3/B4分别219/501断言。此前目录缺失及未跟踪文件导致的原失败报告保留。
- 固定原生计划11例、153事件：`ar3-author-scenario-analysis/native-preparation/runs/ar3-native-r2`。实际执行会话5705 exit0，各case行为符合预定判据。两条final_flush故障均完成4/4事件后后端exit1、分析exit1；sparse后端exit0、分析partial/exit2，未伪造零值。
- 主审直接复核553个完整文件集合/SHA、11例总数和逐run、原退出收据，见 `ar3-integrated-r2-tracked/native-primary-raw-review.json`。
- Franklin执行后只读独核553证据文件、107原生产物、35退出收据；B4复算84条逐事件记录、null/低计数/20批边界，B3核摘要与计分计数、归一化与输入。未重跑后端或原分析器。报告：`independent/ar3-native-results-review-r2/review.md`，结论收据 `engineering-verdict.json`。

## 保留边界

B3三例69事件未启用event_edep，不能声称153事件全部有逐事件CSV证明。受控final_flush异常发生于真实Flush调用后，不是磁盘硬件故障。有限量恢复不证明物理模型精度。

benchmark报告中非null数值与quantity状态矛盾的额外防御，以及B3误差列与moments的全量交叉自洽检查未纳入本片；没有证据表明当前producer产生这些矛盾，不擅自改科学公式。本次审查不替代phase、其他进程退出路径、跨平台交付或AR3总验收。

原生执行器的初版参数键名及收据覆盖缺口已在执行前修复并独审，旧计划与失败/审查记录保留。修后的执行批准仅用于这份固定计划，不能转用到后续不同源码或程序。
