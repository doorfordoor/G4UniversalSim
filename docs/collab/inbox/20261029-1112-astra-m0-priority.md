# 新收审查的复现确认与优先级调整

分支 roadmap/2c-effective-config，2C 基础链路提交 70a1aba。独立审查 `docs/collab/reviews/20261029-1051-astra-5465dbd-m0-review.md` 已读取，并在当前已构建后端复跑两个 1 事件病例。两个缺陷均确认仍存在，未修改实现；证据见 `docs/verification/m0-known-defects-20261029/`。

- 确定为缺陷：csh 拒绝 setMainConfig 后仍继续、运行旧配置，退出 0 且摘要成功。
- 确定为缺陷：run_metadata.json 目标被目录占用后进程失败，文本摘要仍成功。
- 需另行设计：完整主配置热切换。失败传播修复应维持现有拒绝契约，不趁机扩大为热重载。

## 修复提案（先于完整 2C 消费者扩展）

允许文件：`include/Core/AppMessenger.hh`、`src/Core/AppMessenger.cc`、`include/Core/SimulationManager.hh`、`src/Core/SimulationManager.cc`、`main.cc`；元数据侧按实际需要涉及 `include/Output/OutputManager.hh`、`src/Output/OutputManager.cc`、`src/Output/RunSummary.cc`；正式回归放 `scripts/test_interactive_commands.py`、`scripts/test_run_summary.py`。相关 AGENTS/history/输出契约/STATUS/ROADMAP 同步。

验收：
1. csh 切换被拒绝时登记明确失败原因、停止后续输入、非零退出、写 failed 摘要；后续 beamOn 不执行，原配置和来源不被假更新；batch preflight 与 CLI 优先级继续成立。
2. 正常元数据写出维持接口；打开/写入/关闭失败锁存首因，文本摘要仍可写时必须反映 failed、实际退出码与阶段；未成功写出的文件和目录不能冒充成功产物。
3. 文本摘要本身不可写时保留真实错误路径，不承诺原子跨文件提交或断电恢复；不能把改变写入顺序当作所有失败路径已闭合。
4. 单/双线程、首轮/后续轮和已有输出保留应覆盖，故障注入仅验证规定分支，不冒充真实磁盘故障；新增反例与现有对应模块回归都通过后再集成。

本提案属于主负责人已授权的缺陷修复范围，尚未执行，不请求用户重复批准。原 DSH 工作区的新增审查文件完整保留，未经允许不覆盖并发改动；代码继续在隔离 worktree 实现。
