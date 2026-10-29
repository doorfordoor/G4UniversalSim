# 中间证据检查点（非最终CI判定）

M0 run40931654093已completed/success，两job success。官方ZIP：Ubuntu12921734390 sha256:dfb89e22d1f2175667b31e0f204352f04984573bf3f50e7f2baefb393ade76cd；Windows12924085065 sha256:740a786475e5adad3be307f13cc278edf17d70576acbf9e3a8e666efc37c193f，均落盘核对匹配。

4报告：每平台static21/gui37，strict全部0、case集合/head/sourcefp/testsfp/tracked gate均与freeze一致，git_dirty=false。原报告、日志和ZIP未改。M0原始run/jobs/artifacts及两份完整job日志已保存。

Linux run40931653660：UTC18:44:10，11.3 job123651349959已至integration，11.4 job123651349706仍backend，均运行中、无失败步骤。等待实际终态、完整4profiles/平台、2ZIP/2joblogs后再跑最终collector与逐日志独立原字节hash核验。

下载临时URL仅内存及stdin管道使用，未打印或写脚本/报告；无凭据读取，无workflow触发/重跑/取消。2次连接器状态传输错误原诊断单独保存，均一次只读重试恢复，不当作CI失败。
