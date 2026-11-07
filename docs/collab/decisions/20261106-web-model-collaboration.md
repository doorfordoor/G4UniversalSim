# 网页模型辅助协作约定

记录日期 2026-11-06。用户授权根据任务需要使用 Codex 中的 GPT6-sol(web) 或 GPT6 Pro(web)，并要求将方法纳入持续监督。主审负责调度、核实发现和最终验收。DeepSeek 负责实现与自测。

## 适用场景与分工

- GPT6-sol(web) 用于限定范围的第二审查，包括架构与生命周期、代码边界、统计判据、文档和配置语义一致性。也可在明确授权的证据目录中独立复演冻结程序并复算原始输出。首个 H3 只读复核已验证独立任务能够读取仓库、写指定审查文件并正常完成。
- GPT6 Pro(web) 可用于需要更深入推理的疑难定位、互相矛盾的审查结论、复杂统计或架构方案。调用前核实任务界面实际可选型号和标识。本记录尚无 Pro 型号的调用实绩。
- 主审逐项核验建议，筛出真实反例和最小修复范围，再交给 DeepSeek。辅助模型的结论需经主审核实后用于验收决定。
- 用户描述网页额度充裕。调用仍按实际服务可用性和限制安排，以有效交付为目标。

## 已验证的使用方法

1. 使用 Codex app 的 list_projects 匹配 D:/Geant4/G4UniversalSim，再用 create_thread 创建独立本地任务。已验证选择 model=chatgpt-web/gpt-6-sol、thinking=high、projectId=local-df94aba4ac1f087eb9561bbbf0496ca1、environment.type=local。
2. 请求只传目标、冻结合同、候选身份、有限文件范围、输出文件和停止条件。优先只读审查，审查结论写入约定的 D 盘 docs/collab/reviews 路径。主审仍使用 C 盘独立审查工作区。
3. 保存 threadId、hostId、模型选择、输出路径和 wait_threads 返回的 cursor。用 wait_threads 查看完成或注意请求，完整结果需要时再 read_thread。后续同一审查方向优先复用原独立任务，通过 send_message_to_thread 发送具体后续指令。用户已授权在本项目持续协作中调度这些辅助任务。
4. 同一文件保持单写者。DeepSeek 开始修复前保存被审版本的源码指纹或快照。若辅助审查与实现并行，审查必须绑定不可变快照，报告注明基线。
5. 原任务 running 或状态未知时先核实原任务。完成事件与实际文件均需检查，然后主审合并结果并推进当前清单。

## 跨后端限制与恢复

本机网页模型子线程曾出现 ChatGPT Web cannot read this encrypted cross-backend subagent payload。项目采用独立本地任务传递简明可读指令，并在其当前环境中读取仓库文件。遇限流、容量不足或工具错误时记录实际诊断，保存已完成工作与任务标识，按实际条件恢复。

## 当前已验证任务

| 字段 | 值 |
| --- | --- |
| 标题 | H3 平行世界计分只读复核 |
| threadId | 01a1b16c-1865-7812-b4e2-43210d7ffc00 |
| hostId | local |
| 模型选择 | chatgpt-web/gpt-6-sol，high |
| 结果 | completed，已核实终态与文件 |
| 游标 | 9c7b13d0-57cc-4635-b795-2fff548d3c9d:8 |
| 审查文件 | docs/collab/reviews/20261106-h3-web-independent.md |
| 状态登记 | out/collab/desktop-bridge/context.json 的 webReviewThread |

本次协作确认 H3-2 首版的交叠、名称冲突、材料匹配、有效配置与逐 run 收据等缺口，主审已合并交付 DeepSeek round114 修复。原任务和回执身份以 CURRENT-SUPERVISION 为准。

## 独立运行的补充实绩

首版程序已复制到 out/collab/h3-independent-r1/bin/G4UniversalSim.exe 并核验完整 SHA。网页独立任务对 overlap、derived_name_collision、over_cap 三例执行 dry-run，均 exit0 且生成摘要，单元数分别2、5、8192。主审已读回原stdout/stderr、摘要及程序SHA，保存 supervisor-verified.json。此前主审执行通道的 Access is denied 原记录保留，后续可通过该独立任务通道验证冻结候选。

方法是先固定程序和输入身份，约定专属输出目录、明确命令与范围，由辅助任务执行并保存完整原始产物，再由主审核验。开始运行前需确认所有正在执行的任务使用稳定产物，避免引用 DeepSeek 正在重建的程序。

完整backend复跑的临时目录经验已经验证。2026-11-07，冻结14b9f29e程序的三用例首轮因默认D:/Temp访问拒绝而0/3，原报告保留。仅对该测试命令设置TEMP/TMP为项目内专属证据临时目录后，同程序、同脚本复跑3/3通过，39690次执行断言。后续独立运行可使用已授权项目内的专属临时目录，保留原失败记录及进程级环境设置事实。主审已重新核对日志、源码和原始输出哈希。

## 按需增加网页对话的授权（2026-11-07）

用户再次明确：如有需要，可以开更多web模型对话辅助。本项目可按具体审查需求创建多个独立网页模型对话；优先复用已有合适对话，确有可并行且不重叠的范围时再新增。各任务绑定稳定候选/快照与独立输出路径，例如科学输出比较与PID/资源观测可分别二审；保持单写者、主审汇总与最终验收。创建后登记实际threadId、hostId、模型、cursor和任务状态，先核原任务再续派；不把授权或派工算作交付，不因额度充裕增加验收项目或无必要工作。
