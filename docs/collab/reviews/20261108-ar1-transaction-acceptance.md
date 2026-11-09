# AR1 几何加载事务切片签收

2026-11-08当前主审签收本切片通过。AR1整体未关闭；box/tubs及R1-AUD-11、R2-02/03继续实施。

主审D树全新MSVC/Geant4 11.3.2构建exit0，6相关回归全部通过、4744断言；独审Newton从C树独立重建，7入口全部通过、4768断言，均0失败/0跳过。8事务场景覆盖重名、parent缺失、第二叠加失败、投影异常、非法解析、早期校验、保留用户与清空用户成功。失败保留完整已接受状态和真实读取账本，成功整体更新来源与generation；旧作者4项失败原件保持。

两树源码指纹同为 `24f5ec8634e5c0a4928ce311e17104f9ccb1ebbba0d1d338fcdd09fad4815756`，测试指纹 `603ff7b6121e53659e22c0e971480946530d8dfc775ed450704028b03591a4d7`。各自HEAD、二进制和报告身份分别记录，不混称同一次构建。源码跟踪门、首尾身份与严格证据门禁均通过。主审直接重算两报告逐日志SHA、唯一探针计数、状态及首尾身份，见交叉核证（`out/collab/20261108-ar0-ar6/ar1-primary-r2/primary-cross-check.json`）；独验报告（`out/collab/20261108-ar0-ar6/independent/ar1-native-r2/review.md`）及同目录audit-receipt.json保留实际命令与退出。

边界：未构造Manager的空runtime registry事务，不证明Geant4热世界回滚；全局EffectiveConfig revision及非空历史runtime evidence不冒充动态覆盖。未验证任意内存/OS故障，不扩大科学支持等级。独审A5残留零线程进程经显式清理后有信号结束，异常原记录保留，不称全部进程自然exit0。

当前切片工作区仍未提交；可回退原字节、独立候选与报告已保存，后续阶段提交须限定文件，不混入既有用户修改。MR1尚未触发。
