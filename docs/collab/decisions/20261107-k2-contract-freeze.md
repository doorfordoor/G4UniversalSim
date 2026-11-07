# K2-1合同独审冻结与K2-2实施边界

2026-11-07。固定清单20261107-k2-closeout.md保持。主审已核原DeepSeek round156/turn122首稿、round157及同项补充round158/turn123终态；作者完成不直接视为验收。K2-1现通过，允许K2-2实现；K2-2/3/4尚未通过。F3资源仍inconclusive，原5%及科学标准、未关闭状态和停止追加性能批次的边界不变。

冻结合同为[作者r2](../outbox/20261107-k2-contract.md)，原字节SHA-256：
`e27f5a81c83b7af554a0097e4a96ccc0965cdbe3872ccec7dd5f859697931b4f`。
参数SHA `b9b045630e8c7a8bd9530d3747bb1620fd3784a6a56a75b53c4946e0d2cb9332`，回执SHA `697d6bcd46511b5c79a8c0d65dc3e61e0f5e0415ebffc0faabd28b49305a9910`。原r1、网页快照独审及最终r2保存在[合同证据](../../verification/k2-contract-20261107/README.md)，不覆盖原拒绝意见。

主审独立核对：314份原闭包文件实际SHA全部匹配；配置读取器直接返回原字符串、材料/几何消费者按进程cwd加载，故修正为导出根下project/config引用；现有generated writer确实先写绝对路径，必须隔离生成后白名单改写。CMake两个组件以标签component归类，名称分别为h2_volume_scoring_check和parallel_scoring_component。OutputManager统计表明确含run_wall_time_s及fom_per_s，因此只排除这两列比较其余科学列，纯科学CSV仍逐字节比较。网页第二审查与上述实证一致；其未读取的源码边界由主审补核，不外推成构建或物理验证。

以下是实施前消除含糊的最终字段定义，与r2共同冻结；冲突处以本决定为准，不另派一轮整份报告修订：

1. 运行cwd固定为导出根；main.ini材料/几何/并行引用指向project/config，macro为project/macros/run.mac，output在runs下。实际默认模板config不能被所选项目误读。毒化反例在单独导出副本上做，保留原manifest/原包身份与变更记录，不把改过的副本称原包字节未变。
2. generated输入是派生文件，不虚构一个稳定的原始磁盘文件：inputs的source_kind=generated、original_path=generated:逻辑名、sha256_before=null，sha256_after为改写后的真实文件SHA。含临时路径的writer中间文件及其原SHA只进独立审计证据，不进manifest。所有实际读取的外部源文件仍做R10前后SHA核对，不放宽输入变化拒绝。这样P3仍只允许manifest.created_utc变化；project.name取稳定的源项目/运行名，不取不同destination的目录名。
3. template_identity.manifest_digest指模板manifest声明的成员内容digest，不指该JSON文件自身SHA；computed_digest按同一最终模板相对路径、SHA行算法实算。许可证从源位置映射到licenses后的目标路径参与正式模板身份。manifest字节SHA可另记，不能与内容digest混用。1862a858仅为历史原始消费者身份。K2-2正常实现后冻结正式模板manifest，开发/打包在同一候选上比较；修改模板后重新生成实际身份，不硬编码旧值。
4. P5–P8的构建/运行观察属于限定集成与K2-3双平台证据；static脚本只核其静态布局/命令/闭包部分，不冒称已运行。复用现有正式入口、SDK、脚本/命令即可；不新增通用验收框架。CTest用-L ^component$，实际名称集合恰为上述两个且都通过。
5. GUI集中翻译与既有六链同步所需文件纳入本功能窄范围：core/i18n.py的导出消息、gui/docs/中文快速使用说明.md、docs/功能支持矩阵.md、docs/开发路线图.md、gui/AGENTS.md的导出事实。其它范围仍按合同§9；K1行为、普通writer默认行为及CMake默认OFF行为保持。打包版导出不得依赖开发目录、Git或未随安装包分发的packaging模块。

支持仍限S-A示例07与S-B generated单目标及合同白名单。拒绝未知/越界特性，不改物理源代码，不扩大高级物理能力。工程源码自身无根LICENSE只陈述事实；不能凭本冻结补造许可或把依赖说明称捆绑SDK。

本次仅完成消费者/合同静态审查及身份核对，未实际导出、构建、运行或观察新GUI。作者合同doc_links已检查，主审限定正式doc_links为1例11执行断言、0失败0跳过并通过严格证据；它不是产品功能验收。K2-2由DeepSeek实现自测，主审独审后再进K2-3两平台独立构建、真实运行与受控C++修改。
