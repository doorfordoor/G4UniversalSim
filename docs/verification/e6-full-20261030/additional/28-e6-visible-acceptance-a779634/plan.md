# E6 Windows 可见验收准备 — a779634

冻结身份：`a779634483d1f077357433c532ccb0d9e3dc5517`，准备时 tracked clean。134 manifest；root 的 Windows session51778 与真实 CI 尚在运行，本计划不宣称其终态。此前5bf计划保留原身份，不覆盖历史。

当前状态：**纯文件准备完成；未启动 GUI、桌面操作或后端运行。** 用户尚未回复解锁。只有明确解锁并由 root 通知后才启动；不探测锁屏。可见 UI 验收属于工程交互证据，不是物理验证。

## 已准备资源

- `resources/migration`：v5项目、占用目标、源硬链接、未来版本、损坏JSON、10**100投影越界；`preview-reference.json`为当前core只读计划，v5→v6。尚未发布迁移副本。
- `resources/snapshot`：真实冻结writer生成的标准包，混合材料实际输出2.8 g/cm3、Si:0.25/O:0.75，几何Target尺寸3/4/5 mm，源7 MeV、FTFP_BERT/default_cut0.7 mm、直方图42。含未输出禁用草稿；包写成后更改外部原件，供证明包内当前输入独立。专用snapshot loader只读检查已通过，notes见resource-index。
- `resources/duplicate`：7个真实标准包：seed43、seed缺省、seed0、陈旧snapshot/main改为3/83/actual_main_run、内部Unicode及尾NBSP、ASCII外围空白、threads1025。每个main已用窄helper只读检查，期望值见`resource-index.json`。
- `resources/current-project-7-999.json`：与源包不同的当前UI状态7/999/unrelated_current_run。供后续UI显式打开；现在未加载。

准备器只提取正式smoke的fixture函数，未调用其main、未构造QApplication或窗口；将Python占位exe换为实际Geant4候选路径，将snapshot样本23事件改为2事件。进程启动审计钩子拒绝subprocess/os.system等路径。资源58文件均已哈希；不执行任何macro/事件。当前exe哈希只是候选文件身份，不能证明与冻结构建对应，须对照本轮最终full报告再运行。不要直接重跑准备器，它会拒绝现有resources以免重复分配。

## 解锁后可见检查顺序

1. 重核HEAD、clean、报告及exe身份，读取computer-use技能，以新鲜应用/窗口清单识别本轮唯一窗口`E6 Windows acceptance a779634`，只操作/截图自己的窗口。旧native图是锁屏；Qt自渲染图仅布局参考，不作可见验收替代。
2. 打开迁移预览，观察输入/输出版本、变更、阻断、验证边界。新目标必须不存在；成功后源hash不变，当前项目不自动切换。依次试原文件、占用目标、源硬链接，确认拒绝且各自hash不变。损坏/未来文件不能残留可写旧preview。用越界项目从普通Open、Recent或Snapshot入口核对报错级别和当前project/path/widgets/package状态完整保留；只称文件导入可预测投影失败保护，不称任意页面异常回滚。
3. 从真实标准包历史入口恢复snapshot：当前材料/几何来自包，编辑参数来自snapshot。可见“消息与文件”详情及日志需说明重新验证/生成，不恢复手改main/macro、未输出草稿或历史成功，无无条件模态information。普通Open仍拒绝envelope；另选新路径保存普通项目、重载并重新生成，比对实际输入，原包不改。首次生成是待执行文件动作，不可把现在loader检查写成GUI已验收。
4. 载入7/999当前项目，再从各源标准包Duplicate。普通样本后续Run最终CLI必须取main实际threads/seed/name，保留当前所选backend；seed缺省不带当前999，seed0保留0，Unicode尾NBSP不能被strip。陈旧snapshot不得覆盖main。threads1025大于当前真实spin最大1024，若copy已创建，应提示具体路径“副本已创建，未载入、未运行”，当前状态不变且无进程。记录copy前后文件hash与各次状态。
5. “实际最终CLI”优先在可选真实2事件时记录Run入口实际启动参数/工作目录及Inspect收据。若只使用拦截runner.start的可见harness，须明确是最终命令构造检查、无模拟执行；合成Inspect不能冒充真实后端校验。正式offscreen CLI证据仍独立保存，不能移植成可见实窗证据。

## 可选轻量真实2事件（现在禁止）

仅在root确认本轮exe未被并行替换、用户解锁后，对本目录独立简单标准包运行2事件；不要直接启动20事件/千万取消的旧Q1脚本。真实Inspect→Run，保存最终CLI、exe/input hash、新summary/metadata、逐run planned/completed、独立run_result状态。成功须正常退出且2/2事件等既有工程门禁成立，不要求每worker都分到事件。超时先检查自身会话/进程/产物，不盲目重跑；只关闭本轮自己窗口。此项仍不能验证物理正确性或一般无偏性。

## 身份核对与待办

`preparation-manifest.json`：13个当前源码/正式smoke/runner文件hash及HEAD blob；与5bf旧清单7路径的hash全部相同，旧计划三文件另外留hash，未改旧目录。`resource-hashes.json`：58个新样本文件hash。`resource-index.json`：包路径与预期run设置。

待办全部pending：用户明确解锁、root确认可launch、最终full/CI终态与exe关联、可见窗口操作/原生截图观察、实际Run命令、可选2事件及最终验收报告。无窗口/运行会话由本准备任务占用。prepared_not_launched。
