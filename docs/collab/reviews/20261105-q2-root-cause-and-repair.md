# Q2-5 主审直接调查与修复独审

## 已定位的原因与修复范围
产品864bc036、后端SHA f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f，Windows Geant4 11.3.2。

原配置是10 MeV电子在10 mm G4_Pb靶内对eBrem作factor10发生偏置。问题不是CSV合并或简单漏乘交互权重：C1 4095个初级issued步逐条满足局部存活/交互似然更新，13421个被门控的初级步没有额外权重变化。证据out/collab/q2-primary-likelihood-audit.json及原C1流。仅排除本记录内这些具体假设，不证明整个物理无偏。

关键独立对照（不是旧结果重算/重试）：

|配置|独立批次|biased/analog剂量比|99%差值区间 Gy/event|
|---|---|---|---|
|原factor10、原步长|16+16|0.405794676|[-7.89829e-11,-5.00272e-11]|
|factor1.2、原步长|新biased16，引用原analog16|0.974554949|[-3.48979e-12,-2.03468e-12]|
|factor1.2、双方Target max_step=.01 mm|新8+8|1.000044886|[-1.451914e-12,1.461625e-12]|

第二项已经显著偏低，不能把原差异全归因于factor10的稀有大权重样本。第三项改变了双方的步长上限，直接显示有限步长的敏感性：连续能损发生在整步上，发生偏置的存活权重随路径变化；项目与原生计分器都用步前权重计分，原生一致并不足以证明带电偏置剂量正确。Geant4能损过程还包含能量相关截面及积分拒绝机制。本实验定位到这些有限步长过程的组合，尚未将各项贡献单独定量分解，尤其不能声称完整解释了factor10全部59%差异。

依据：[Geant4发生偏置说明](https://geant4.web.cern.ch/documentation/pipelines/master/bftd_html/ForToolkitDeveloper/GuideToExtendFunctionality/EventBiasing/eventBiasing.html)的推导明确限于无连续能损的中性粒子；[能量变化的截面修正](https://geant4.web.cern.ch/documentation/dev/prm_html/PhysicsReferenceManual/electromagnetic/energy_loss/integral.html)解释带电过程的积分方法。文档分别标识11.2/11.4，不能冒充11.3.2特定结果；本机v11.3.2实际源码G4BiasingProcessInterface.cc沿步更新已另行检查。源码在out/collab/q2-biasing-c1-review-r1/g4-sources/。

一个说明机制的解析反例（不是本机10MeV结果的校正公式）：设截面常数lambda、连续能损率c、偏置倍数f，第一段长度X服从Exp(f*lambda)。单段以步前单位权重计分cX，其均值是c/(f*lambda)，而analog是c/lambda；沿段真实似然是exp((f-1)*lambda*s)，积分计分才恢复此理想模型的期望。该反例说明“步末权重更新正确”与“整段连续沉积估计正确”并不等价。真实Geant4包括变能、散射、离散沉积和次级，不能直接把这个理想积分乘到总Edep上。实际处理仍是限制本病例步长并独立验证。

修复选择：保留计分契约、生产物理算法和原失败；为此病例使用factor1.2与双方.01mm步长上限，并用未参与诊断的固定32批作独立留出验证。同步修正科研使用说明。没有理由将步前权重一律换为步后或中点，也不能用一次均值比标定剂量。这个修复针对基准配置与适用声明，不是所有带电偏置算法的通用修复。

## 当前验收
round94交付、turn79已完成，实际Flash/Max。独立留出32批64000事件的比值0.9987410407、99%差值CI[-8.4961031e-13,5.7750840e-13]、半宽0.6603%；428原比较检查及439主审核对通过，544原件哈希一致，3批3733398命中独立重建、7负控独立复验通过。r2限定病例签收；原factor10失败与一般带电偏置限制保留。最终证据见docs/verification/q2-biasing-repair-r2-20261105/README.md；Q2整体未关闭。

## 原件与执行偏差
原v1科学失败保留。C1实际6次、首轮9原件覆盖事实保留，不再要求补造历史。双StartTracking发生于首次步之前，当前记录内未形成中途计数重置。
主审32次新诊断的完整原件在C盘out/collab/q2-root-factor12与q2-root-step01；D盘out/collab/q2-root-investigation/*-originals.zip已解压流逐文件SHA核验，originals-manifest.json记录清单，C原件继续保留。两个zip分别54,404,736与1,394,720,175字节。诊断没有将输运计时注册为主终点，不据其比较性能。
