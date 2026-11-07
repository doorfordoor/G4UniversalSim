# K2-3 最小运行修复r5独审冻结与恢复

2026-11-07。依据原固定清单与20261107-k2-native-runtime-minimal-fix.md，仅签收两项最小修复，恢复K2-3。整项双平台验收/正式云CI均尚未通过。

产品冻结56b1da77704223a8b84e3256c915c8242aad8946，D/C同产品；r5原回执7a8db9cf…，六文件原SHA及全部309规范模板成员独核一致。正式模板1fa4e29430ee813a5736329b9fd2677e178dbac11ceabb289ed828055de8df29，manifest 4f512a9d…；唯一新增scenarios/semiconductor/niel/si_proton.csv，其原内容未改。C实际检出template check exit0/problems=[]；原b91、旧失败身份均保留。

独立固定源码快照专项exit0/3551执行断言；同候选C真实检出的GUI专项exit0/33断言。受限归档GUI首次缺既有shielding_coating依赖失败，转真实检出后通过，原失败保留，不要求修产品。新导出主INI未手改，Linux原生S-A200/200 completed与H2组件均exit0；此有限运行复用先前仓库外本机构建，236个编译输入字节与新导出逐个相等、真实exe SHA已记录；**不是新候选重新构建或K2-3全通过**。主审Windows新目录仍拒绝，Linux首个运行缺SDK逐数据环境变量的失败保留；改为复用现有micromamba激活环境后上述运行通过，未改全局环境或权限。完整证据out/collab/20261107-k2-implementation/independent/r5/acceptance.json。

作者r5覆盖了主审original-42be-failures/identity.json索引，原索引字节未保留；原始日志/能力/产物SHA快照和consumer-counterexamples.json仍在，新r5/failure-evidence-integrity.json据实际原始文件重新列索引。主审签收该记录限制，不伪称旧索引原样；不影响两项真实反例和修复验证。后续严禁作者写主审independent目录。

恢复原K2-3有限矩阵：从新候选原始导出取证，两个component的精确CTest集合、双平台S-A200/S-B1000、确定性、P7/P8、一行C++修改、真实产物/依赖/摘要/比较均须完整。复用SDK和确有不受影响的旧编译/依赖/运行证据，保持旧SHA，逐项说明编译输入/输出数据等价映射；不为换一个导出器提交号盲目重建同一C++。所有新构建先核缓存CMAKE_HOME_DIRECTORY，绝不复用指向另一个树的缓存。修改后科学判据与F3限制保持，不再扩大范围。
