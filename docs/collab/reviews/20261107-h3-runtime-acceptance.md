# H3-2 运行时验收

日期 2026-11-07。主审裁定本清单项通过，下一项为 H3-3 配置与文档入口。H3 整体阶段继续进行。

## 接受身份

程序 SHA-256 为 14b9f29e7b71bac9beb1c582582c7deeab3e27d73faae958ee46d083fcd09537，源码指纹为 860b54b2982f1d50d2d414b74eb21864243250874d7a4770a1b4a94245dff114。HEAD83c0b139，未提交工作区的24个源/测试文件及两个程序已保存于 out/collab/h3-independent-r4。该身份仅用于本次运行时验收。

## 主审核验

主审核对了[独立复审](20261107-h3-backend-fix-r3-independent-web.md)的原始产物及A-I源码修复链。四个已列反例均得到正确结果，原输入字节已核SHA。既有三个backend用例独立复跑为3通过、0失败、0跳过，共39690次执行断言，报告 out/collab/h3-independent-r4/verification/20261107-015428-226c9a5c/report.json。主审重算三个日志哈希，核当前24个文件与冻结快照一致。

生命周期案例真实完成20/20事件，质量copper、平行water，材料证明unknown。主审独立重算metadata的15个文件SHA及run_validated收据中的12个文件SHA，均吻合，摘要与metadata的16个路径集合相同。验算记录 out/collab/h3-independent-r4/supervisor-acceptance.json，四反例核验另见同目录supervisor-fixed-regressions.json。

首次三个用例在D:/Temp访问拒绝的0/3报告保留于verification/20261107-015342-39283d50。仅将测试进程临时目录改为项目内专属目录后，以同程序/同脚本复跑通过。所有早期源码、反例与失败记录继续保留。

## 验收范围与后续门禁

本项接受配置解析/拒绝、真实box及grid构造、dose/fluence专用路由、输出身份/归一化接线、动态约束与线程生命周期的既定工程证据。零命中hits惰性缺席、受支持输入不增Stage B注入、未知材料用unknown均按原冻结决定执行。Case M完整事件集合/统计矩及预注册Welch基准仍由H3-4执行，H3-3入口与文档、H3-5双平台正式回归/云CI/必要原生操作继续按固定清单完成。

继续沿用Q2科学适用域限制。本次本机Windows/MSVC/Geant4 11.3.2证据不替代后续Linux或正式发布证据。
