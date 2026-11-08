# AR1 主审签收：几何事务、规范参数及关联审计修复

2026-11-08，当前主审对话按AR0 r3、AR1切片合同及原审计关闭判据签收：**AR1本轮约定范围完成**。R1-AUD-11、R2-02、R2-03关闭。接续AR2；此时AR2–AR6未完成，MR1须待AR1–3实质完成后才进行，不能用本次单阶段签收替代。

## 候选与身份

原生验证基于HEAD `25487eb13432c5f4e968aa405607056f6a8febce`的明确脏树候选r5；冻结清单为`out/collab/20261108-ar0-ar6/ar1-integrated-r5/freeze.json`。

- 产品source：`382027858d36a1f6c72c18e8bd09760fc77e8ce1413c57801f6c9abe0735a751`。
- 测试：`b19dce0a7533bd897b34e1ec5e7f9e651850b8e21484a2ebc02ca721ea4651ad`。
- D实际新构建主程序SHA：`d54a7a3b8cd088c6a74173fdbf98556315ecab39cc6cffd4a06aa80fb49d7dc6`；C独立新构建SHA：`f70916e0ffca4ebf054d6bdb9054fb19fbeba583f0575ca4cb0adb96d942a154`。两树源码逐项相同，Git HEAD、路径及PE字节不伪称相同。
- r3→r5只修组件测试接线/精确诊断期望和模板清单；产品源码及两个原生几何探针未变，D显式复用r3新二进制。模板315成员identity `54ac9af51e5a645cf18e413289d9d286d77419d0de7465d12b894a42cb344c4b`。后续文档/提交身份须另记映射，不追改本次构建与测试收据。

## 实现与验收

|范围|实际成果|证据与边界|
|---|---|---|
|几何加载事务|候选解析/校验成功后才替换已接受模型与来源，失败保持既有状态|既有[事务主审签收](20261108-ar1-transaction-acceptance.md)及r5再次原生验证；不声称热world回滚|
|box/tubs规范值|INI、直接C++及boolean工具消费同一临时规范参数；保留全长/半长、单位、别名及C++兼容入口|新shape探针实际G4Box/G4Tubs读回；187条包装器断言，包含实际构造/拒绝与旧形状路径；其它形状仍走有名兼容路径|
|R1-AUD-11|同region按粒子检查同值/互补/冲突；完整树冲突在创建内核对象前拒绝；构造时保留已接受其它粒子cuts|6例真实内核读回及正反序；旧基线2pass4fail保留；另固定8次有限输运及独审180检查通过，见下文|
|R2-02|按实际孔数生成有孔/无孔几何，零或舍入零不再生成空副本表|静态19例和真实16合法生成包初始化；旧zero/tiny仍按指定空副本原因拒绝；非零同seed及禁用分支保持|
|R2-03|半导体计算几何值使用17位往返精度，不放宽后端容差|300um分7/11及不整齐尺寸原生初始化、原10/1/5片和非法片数覆盖；旧7/11输入按原分区错误拒绝，不改历史科学输入|

独立原生15项通过证据由首批6项成功与修正执行路径后9项成功组成，有效断言11485。不是一份伪造的15项绿色报告。原15项6pass9fail及外部临时路径9fail保留；原因由同二进制限定dry-run定位到当前执行路径可写范围，未改ACL或系统防护。最后9项正式报告严格身份门禁exit0；首批只对6个成功记录按原身份复用，失败报告整体仍失败。四个旧生成输入负控均为指定诊断、后端exit1。独审：`independent/ar1-integrated-native/review-final.md`及`audit-receipt-final.json`；主审另读原报告/日志重算20冻结文件、全部15项覆盖与身份，`ar1-integrated-r5/primary-cross-check.json`通过。

## 构造消费者与有限输运

- H3新候选工程4进程，每例2000事件；A/R-SAME/A2/A2f通过。独审逐字节核50产物、4日志并独立CSV核71检查。`independent/h3-adapter-review/REPORT.md`签工程范围；B/C科学批次、M、R-RUNTIME/R-COMP未由此签收。AR2触发时仍须原冻结完整科学协议。
- K2 Windows新导出S-A external与S-B generated各自独立Ninja/Release构建，各两组件真实CTest通过，200/200与1000/1000事件、线程/种子/source均匹配。14命令exit0；两原始导出闭包及六binary首尾一致。实际根`D:/Geant4/AR1-K2-r5-Windows-r2`；独审`independent/k2-adapter-review/runtime-r2/REVIEW.md`。仅本次Geant4 11.3.2 Windows有限回归，双平台安装/导出扩展仍归AR5/6。
- AUD-11有限输运manifest `3efc92fff10fde6109bcd23227b3f289cf9a397228c20789500e077abc01ea13`：旧/新各互补正反序及完整显式参考，共8进程、各200事件、10MeV电子、单worker、seed20261108。新互补与对应参考逐事件能量和hits累计相同；旧互补确有e−或gamma cut丢失，新值完整且顺序无关。所查Si couple能量阈值均为0.00099MeV，本固定样本未观察到所核输运量差异；不推断普适物理无影响或统计等价，不加批追差异。独审`independent/ar1-region-transport-review/REPORT.md`及180检查原数据复核通过。

以上相对证据路径均以`out/collab/20261108-ar0-ar6/`为根。原组件/模板/临时路径/适配器失败保留，未删除失败用例换取通过。A5负控遗留的零线程进程对象经明确路径清理、wait已结束，数值259仍保留；不称所有子进程自然exit0。

## 交接

当前源码跟踪门通过，无未跟踪生产/测试源码。stage提交只纳入明确拥有范围，不吞并其它脏树修改。新增[依赖与实际扩展判据](../decisions/20261108-architecture-principles-adoption.md)沿MR1/2/3落实，不重开本候选。AR1没有新增形状集合、GUI功能、热重载或科研能力；F3与DS/web限制保持。
