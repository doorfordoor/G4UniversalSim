# K1 可信实验工作流：实施契约

基线 e701c7fa5b5b8899d8dd8b9f6a0b4b305614e5c9；分支 roadmap/K1-trusted-workflow。用户授权完整实施、独立审查、矩阵验收和正常集成推送。原 D 盘检出不写入。阶段状态仅在 ROADMAP，过程更新 STATUS。

## 范围与所有权

- 主负责人：接口裁决、GUI/CLI 接线、测试登记、文档、构建与验收集成。
- Sol High 核心写者：新增 core/experiment_workflow.py、core/experiment_identity.py 及专属 test_k1_workflow.py。统一 inspect/validate/apply/generate/run/evaluate/export；注入已有 EditSession/G4USimRunner，不另建历史或进程控制器。
- Sol High 资源写者：新增 core/experiment_bundle.py 及 test_k1_bundle.py。资源闭包、路径重定位、原子导出/完整性加载、重放入口。
- Sol High I1 写者：新增 core/environment_discovery.py、widgets/environment_dialog.py、test_i1_environment.py、smoke_i1_environment.py 及 docs/环境发现与诊断.md。只读候选发现、真实能力与数据探测、SDK/工具链/可选组件、选择与诊断，不拥有模拟状态，不做安装器。
- DeepSeek：独占新增 widgets/experiment_panel.py 设计与实现候选，先交付流程/验证状态/导出交互方案和完整源文件，经本地审查后集成；不让远程建议自动执行。主负责人负责 i18n 与信号适配。实际请求模型/返回模型及失败保留，不记录凭据。
- 独立 Sol 审查者：不参与被审文件实现；审查后才分派必要修复。Terra/Luna/Astra 未列于当前可选工具，不伪称调用；消耗未知。

## 服务与证据契约

工作流绑定完整 WorkspaceSnapshot、单调 EditSession revision 和配置/资源内容身份。apply 在副本完成 F4 producer 校验后通过 F5 replace 原子接受，拒绝不污染历史。GUI 人工草稿编辑继续由 F5 承载。生成复用 package_writer；每次运行独立 UUID/目录，进程只由现有 runner 管理，忙时拒绝重复，取消不得发布成功。

验证层级独立：字段/依赖；后端初始化及几何检查；指定输入真实事件完成；指定参考与判据下物理比较。inspect 的 Configure/preflight 不能冒充初始化。运行完成复用 run_result 并核对 F1 provenance；物理比较要求显式量纲、参考、容差、统计口径和来源，不提供无条件“物理正确”。验证记录绑定配置、资源实际字节、后端二进制/能力、环境事实、随机设置、事件数和判据；未知事实明确 unknown。当前输入或 revision 变化使旧记录陈旧，保留历史，撤销不自动复活。

导出为版本化配置包（不是 K2 工程）：项目模型、材料/几何、macro、已支持引用资源闭包、相对路径、SHA256 manifest、验证历史与重放入口。不复制后端二进制、密钥、用户设置或完整环境变量。未知资源语法、缺失文件、路径逃逸/链接、无法分发的资源明确拒绝或要求显式资源策略，不能静默遗漏；分发权未知明确标记，不声称授予许可。新目录暂存、验证后原子发布，已有目标不覆盖，失败保留原目标并可重试。加载验证所有清单成员并拒绝逃逸/篡改；环境/后端重新选择，历史结果不冒充本机验证。

## 兼容及验收

保持项目 v7、F4/F5、现有运行入口与拒绝边界；不开放 J2 高级编辑，不引入 L1 provider，不生成 K2 C++/CMake。I1 独立记录完成范围及剩余限制；Geant4 11.3.2/11.4.3 沿现支持矩阵，11.2 不自动加入。

反例覆盖：非法字段/依赖、源文件变动及同名不同字节、搬移/中文路径、资源缺失/嵌套引用/绝对路径、陈旧与撤销后的验证、失败/取消/重复运行、导出目标冲突/发布失败/篡改/恢复。真实干净目录完成加载→修改→运行→旧验证失效→重新验证。合成/自动/实窗/真实模拟/物理比较分别计证。

提交顺序：范围契约→可运行实现→冻结整项验收→集成交付。冻结后跑 Windows 全矩阵、Linux 11.3.2/11.4.3 及 M0 两平台现适用回归、严格原始日志和同代 F5 逐例/总量基线门禁；独立代码审查与 Windows 实窗观察必须完成。旧报告不可追改，不降低门禁。必要验收缺失则 K1 保持未完成。
