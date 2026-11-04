# E4 双平台独立复演

Windows 与 WSL Ubuntu 分别通过生产 Qt 窗口动作驱动 shielding_slab 模板，选择真实后端，校验、运行100事件、核对新摘要、导出配置包并在第二窗口重新导入。分别归档结果与原摘要和清单。采用 offscreen Qt，文件选择对话框由复演程序提供路径，非人工实窗。最终两个宿主均按窗口关闭协议释放，退出码0。

首次 Linux 在 /mnt/d 下发布 execution-inputs 遇到 Errno 22，原失败保留。使用 Linux 自身文件系统的 runs root 成功。早期观察程序曾读取不存在的 project.name，随后两个探针虽写出结果但未显式释放 Qt 窗口而在退出时异常；原日志保存在 D 盘 out/collab/e4-independent，正常退出结论仅绑定 drained 两次。
