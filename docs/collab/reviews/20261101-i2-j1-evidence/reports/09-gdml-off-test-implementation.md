# GDML-off 能力依赖用例分支（2026-11-01）

裁决：能力OFF应执行明确早拒绝且无模拟产物的真实反例；不是skip，也不是GDML功能验收。ON必须继续全部原身份/场/事件/物理判据，不改变事件数与容差，OFF断言数不得与ON基线直接等同。本轮按root授权仅改测试，无产品修改。

## 文件与行为

- 新scripts/gdml_test_support.py：从实际--capabilities唯一gdml模板读取严格bool runtime；缺失、重复、类型错误或命令失败即失败，没有unknown→OFF降级。打印独立G4USIM_GDML_TEST_SCOPE。
- 不可用拒绝helper要求明确Geometry capability 'GDML' is not available、非零退出（fields Runner原门禁负责）；检查递归无CSV/ROOT/GDML/径迹等模拟产物。早期拒绝可无run_summary，打印summary_present=false；如果有摘要，必须failed/run_count0/completed0，不捏造摘要通过。
- test_gdml_bias_identity.py：原24份fixture仍实际逐一执行，OFF在读取摘要前检查早拒绝、没有process dump、原GDML字节不变；ON原case-collision/真实双operator/wrapped process等代码未改。
- test_gdml_touchable_identity.py：原5种placement×1/2线程共10fixture仍实际执行，OFF早拒绝+输入不变；ON原复制路径、质量/能量、歧义拒绝及所有容差未改。
- test_fields_a7.py：只给shared_gdml_fields增加OFF分支，1/2线程各实际拒绝一次；ON原共享LV冲突/显式继承/同名歧义和能量判断保留，所有普通层级场与解析物理回归继续完整执行。

## 实际Windows11.4 OFF验证

原venv+实际out/build-i2-windows114/Release/G4UniversalSim.exe，子进程PATH显式使用所选11.4DLL、GEANT4_DATA_DIR用已发布43527文件数据树。

- test_gdml_bias_identity.py probe：exit0，49个目标文件assert入口，24真实early拒绝，无simulation products。
- test_gdml_touchable_identity.py probe：exit0，11入口，10真实early拒绝，无simulation products。
- shared_gdml_fields窄调用：exit0，2真实拒绝，原输入保留。
- 完整test_fields_a7.py probe：exit0，252入口，其他磁/电/交叉/映射/局部/离子/非法场判据继续执行并通过。fields-a7-full-off.log。
- helper负例窄测：成功退出、无关失败、意外评分文件、completed摘要、实际有事件的failed摘要均被拒绝；helper-negative-evidence.json。
- py_compile、git diff --check通过。没有重跑大矩阵或下载/冻结。

此处49/11/252只是当前OFF用例目标文件的探针入口数，导入helper内断言未算入这些计数，不夸大为独立命题数，也不将OFF与ON数值直接门禁比较。ON仍须在Windows113/Linux113/114实际支持组合中执行完整原判据，由root正式矩阵闭合。

## 历史与范围

out/collab/gdml-off-candidate保留本轮全部新log与bias/touchable/fields原始fixture/输出；original-failure-*.log和original-failure-identities.json复制并SHA登记原开发矩阵三个失败。原文件未改、未把旧失败改成pass。能力OFF的新证据只覆盖早拒绝，不称GDML roundtrip、物理场共享、偏置或touchable身份已验证。

另：root test_geometry_a5.py新增OFF三例只读复核未见问题：实际capability分支、import/export明确非零与not available、无CSV和export目的文件、原GDML字节不变；ON gdml_cases/gdml_case_sensitive_sd原调用仍保留。其真实三例exit0证据沿root原身份，不冒充我重新执行。

完成状态：J1首次preview P2已独立关闭，见j1-preview-p2-final-independent-review.md；GDML-off三个测试实际分支及完整A7已过，见gdml-off-test-implementation.md。无剩余运行session。未改产品。root继续正式能力矩阵/ON真实验收。
