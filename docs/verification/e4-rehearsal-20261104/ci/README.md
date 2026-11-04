# Ubuntu 安装验收的磁盘空间

原候选 f7793dcb，运行 41860688699，Ubuntu 作业 126681328482。在 source-and-data 检查点需要 6810606082 字节，实际可用 4751527936 字节，差额 2059078146 字节。原始 GitHub artifact 13340360782 已按官方 SHA-256 和 ZIP CRC 核验并归档，内含 delivery-report.json 和 discovery.json。

修复针对 GitHub 托管 Ubuntu 的一次性作业。它释放固定路径的预装 Android SDK，在安装目录所在文件系统测量操作前后的可用字节，并把实际删除状态写入作业摘要。其余安装步骤与候选 f7793dcb 逐项相同。独立检查通过 YAML 解析、步骤条件、固定目标和 Bash 语法。释放量与完整安装结果以新作业回执为准。
