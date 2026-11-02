# Linux Xvnc 原生文件独立复核

限定通过：真实X11/xcb计划操作和预览链路，不代表整个Agent任务成功。计划操作passed，随后在固定300秒预算到期后进入failed/agent.task_timeout；原始两条failed终态信号保留。一次确定性回环HTTP请求、一个任务、零执行事件、无K1/后端进程动作；原子首尾业务快照字节完全相同。fixture提出e-/1GeV，与proton目标不符，不能将协议成功写成语义或物理正确。

launcher首尾冻结246e4f6、GUI157、tests指纹和Python身份一致；host实际exit0，外层terminal-sync完成，remaining_owned为空且slot_released。HTTP线程停止、listener关闭。Xvnc/twm/noVNC服务已关闭、owned为空、回环监听已消失；子进程原退出码[0,1,0]中的twm exit1保留，不冒全子进程exit0。

这轮是独立TigerVNC真实Linux桌面，经twm与回环noVNC操作，不是WSLg RAIL恢复成功。旧fc-list拒绝、xcb-cursor缺依赖、RAIL显示/焦点异常、镜像坐标误操作导致QA草稿变化、旧observer未启动，以及display run01启动失败均分别保留。共享内存EIO与外部相近案例不能证明本机唯一根因；未重启/重挂/提权。

本复核只读取结构化证据并核原字节哈希，没有桌面操作、PNG解码、UIA正文读取或新Qt进程。视觉结论须读review.json中独立归属的operator_visual_attribution，不能由host退出或图片文件存在倒推。

native-assets-metadata.json仅有scope/path/size_bytes/SHA256/MIME五字段：当前14张Xvnc原图、历史2张WSLg诊断原图，均本地保留。未复制或上传原图/敏感日志；source-metadata.json也仅存路径与字节元数据。review.json是显式白名单投影，没有prompt、目标文本、凭据、计划payload或原始日志。无科学验证、通用NL质量、用户提速、打包GUI/VTK或全平台显示支持的结论。
