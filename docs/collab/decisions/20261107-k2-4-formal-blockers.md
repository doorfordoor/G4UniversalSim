# K2-4 正式验收阻断与最小修复

原正式工程候选：`4bc77b5b80a2d3309cb8f972f33d4110ce1986ce`；产品代码 `b1a7ffbc`、模板 `b2285d11…`。本记录执行固定清单 K2-4，不新增验收项目，不降低标准。K2-3 非阻断限制签收保持。

| 原反例 / 阻断项 | 最小文件范围 | 修复及停止条件 |
|---|---|---|
| M0 run42374151337 两平台静态各49通过/1失败/0跳过；Linux后端 run42374151367 两版本亦在 platform_paths 失败。新K2测试固定README命令含Windows构建目录、两处恶意归档输入含固定盘符，被原扫描器拒绝 | scripts/test_k2_project_export.py；只有确实必要时才改 tools/platform_path_fixtures.json | 使用真实导出预设推导文档命令及既有具名拒绝夹具，保持原攻击类型和拒绝断言；禁止拆字符串逃避扫描、伪加G4USIM_EXE或扩大豁免。原平台扫描、夹具策略、K2导出专项通过后停写交主审独验 |
| 原安装 run42374151336 / Linux job128408194744 在 build-runtime 失败，R8缺CMakePresets.json。ci_delivery源码快照根文件集合漏该模板成员，不能完成原定安装验收 | packaging/ci_delivery.py；scripts/test_install_ci_delivery.py | 根文件复制补CMakePresets.json；原临时origin回归证明实际字节及快照收据成员。主审核真实快照309模板闭包；不扩通用框架、不重编后端。最小修复独验后重冻工程身份，恢复原正式验收 |

原静态/安装日志及下载归档在 `out/collab/20261107-k2-final/`。Linux静态归档SHA256 `8859eef4c3a92ff68a5bbbbc2cca0da4dda68e0e62381981a6a8c7d2ee1a56ef`；Windows静态 `a445edde325ced0bef62d8b061064cae4c6f8ecc83da0c10723ae358a501574f`；Linux安装 `1aec6e3d8d588af662fa01db57af93f555615940cd0465eba0683135918183ce`。旧失败报告不重写，云端原Windows安装任务不抢占。

DeepSeek原会话 turn133 负责修复及有限真实导出入口观察，round179/180/181指导已接收；主审负责独立复验、候选/模板影响判定及正式云证据门禁。产品C++未因这两处反例改变，不据此循环K2-3矩阵。若policy未改且这些脚本不属于模板成员，保留原模板身份并实查；若模板成员变化则正常重算身份，不能伪称相同。

desktop run42374151355 两平台已成功，其范围是冻结GUI启动/正常退出及ROOT helper；不能据此声称K2安装后导出入口通过。CI上传回执/日志不等于已下载完整安装包。源GUI观察、冻结GUI观察、正式安装与独立工程科学数据仍按实际范围分别登记。
