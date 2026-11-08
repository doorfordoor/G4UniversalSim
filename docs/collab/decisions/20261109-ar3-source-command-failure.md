# AR3：源命令拒绝必须进入受控失败收尾

## 新证据与原结论边界

AR3 v3的D/C三项正式测试和严格候选门通过，不代表每个负控均正常收尾。独立C收尾检查发现GPS case22残留未退出进程对象；D有同类对象。原GPS只判断非零退出，随后删除临时输入及输出，无法据此签收正常失败摘要或事后独核600历史原CSV。

主审在 `out/collab/20261108-ar0-ar6/ar3-gps-lifecycle-r1` 从冻结脚本重建一个case22，不重跑科学批次。实际Popen PID69304返回3221226505（0xC0000409），同一进程句柄已signaled且退出码一致；stderr明确记录 `SourceMessenger::SetNewValue` 的 `AIHL_SOURCE_001 / FatalException / Aborting execution`，没有正常失败摘要。源代码的 `ReportCommandFailure` 对普通配置拒绝调用FatalException，与此次实际退出吻合。

随后观察到另一个同命令行对象PID64452、父PID69304，线程/句柄数为0。其创建原因尚未查明，不把它表述为仍执行模拟的线程，也不认定某个Windows组件是原因。D原PID10408及此次64452在保存路径、命令行、父PID和状态后由主审精确强制清理，等待退出成功；强制清理不算自然exit0。C独审及全部旧失败、原三项通过报告保持原身份。

## 批准的有限修复

沿已有Material/Output命令失败处理方式，为SourceManager增加诊断失败计数和最后错误；这不是修改已冻结输运描述的后门。SourceMessenger的标准及未知异常不得仅降级warning后假装成功，也不得对本次可控拒绝继续Fatal中止。

RuntimeSession的batch逐命令检查必须绑定原macro文件、行、文本，设置失败并停止后续命令；没有实际Geant4返回码时明确code unavailable。csh检查必须接入停止读取和最终source错误分类/消息，写failed摘要并正常非零退出。Qt/native UI不扩大为已经完成逐命令同等验收；受控SessionServer的实际入口另按源码核查，不凭名称假定经过Messenger。

精确初始写集：SourceManager.hh/.cc、SourceMessenger.cc、RuntimeSession.cc，以及runtime dispatch/GPS两个测试。先在 `ar3-source-command-author` 隔离交付，不修改当前仍运行的8ab/8ad候选。

## 验证与关闭条件

- 保留原named-source/能量/种子/线程和后续beamOn输入，真实batch及csh拒绝须正常exit1、failed摘要、原错误信息和正确归属；后续事件不能被执行。正常源命令正控保持。
- GPS case22不再以任意非零退出放行。正式证据目录保留实际输入、命令/PID/退出、日志、摘要与原600记录/回放产物；原科学门限及原失败不可改写。
- 新候选独立复核真实进程退出及所属残留，不用强制清理冒自然退出；完整兼容与身份门按影响复验。

此项为AR3运行生命周期中新发现的收口条件，不更改原27项审计编号，也不代表AR3或MR1已关闭。隔离实现、原生验证及独立签收尚待完成。
