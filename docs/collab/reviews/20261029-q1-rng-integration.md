# Q1 R26 随机命令语义提案与接线

## 裁决与范围

确定为缺陷：Geant4忽略`/random/setSeeds 123`仍返回0，`SimulationManager::NoteMacroCommand/ConfirmMacroCommandSuccess`按命令名误报成功。恢复状态原生命令同样没有可依赖返回值，部分CLHEP解析可在损坏文件上挂起。

文件清单：新Core/RandomCommandGuard.hh/.cc（独立实现者q1_geometry），src/Core/MacroPreflight.cc、main.cc、scripts/test_random_command_semantics.py、正式测试清单及契约文档（root）。不改变默认RNG/物理/种子优先级，不补造unknown初始状态。

设计：preflight严格验证种子个数/整数范围与路径语法，执行点读一次状态文件并对独立临时engine验证后从内存提交；不调用不可靠原生restore。csh复用守卫并区分语义拒绝与Geant4数值返回码；只有语义已接受且命令执行成功才记录修改。恢复只作用当前master，不声称恢复已有workers。每事件恢复若没有安全路径则拒绝enable并说明替代方案。

验收：修前clean 4e6fa7a复现；单/双worker、合法种子、1个/非整数/溢出/零截断种子、CLI锁、嵌套macro精确来源、csh不继续；原生保存→恢复、同状态、缺失/空/截断/错引擎/坏索引/校验和；坏输入不触碰当前状态，不输出成功摘要，非零结束；新用例进正式runner，完整平台复验。

实施：接线已按上述接口在main和MacroPreflight建立，等待守卫源码及专项。完整恢复解析细节由同目录q1-rng.md记录；尚未构建或声称通过。
