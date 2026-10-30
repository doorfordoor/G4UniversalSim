# F1第三冻结CI：通过

HEAD `f176d0ed4cea60b7ca5a80ed81017c9404ec1257`。Linux run41028779177；M0 run41028779326。四原ZIP官方digest及解包文件字节、四完整decoded joblogs、12报告与全部414case日志SHA/断言marker已核对，冻结143case按每个profile精确匹配，head/source/tests一致。

严格门禁通过 12/12。失败case 0。未重跑CI、修改源码、启动主exe或操作UI；原证据只独占保存或复用相同字节。

|Artifact|Profile|Cases|Strict exit|非pass|
|---|---|---:|---:|---|
|linux-evidence-11.3.2|[backend](linux-evidence-11.3.2/linux-backend/20261030-085908-442e5e41/report.json)|59|0|无|
|linux-evidence-11.3.2|[gui](linux-evidence-11.3.2/linux-gui/20261030-085807-247d9d38/report.json)|39|0|无|
|linux-evidence-11.3.2|[integration](linux-evidence-11.3.2/linux-integration/20261030-091347-3c389cd8/report.json)|20|0|无|
|linux-evidence-11.3.2|[static](linux-evidence-11.3.2/linux-static/20261030-085714-5a950ea2/report.json)|25|0|无|
|linux-evidence-11.4.3|[backend](linux-evidence-11.4.3/linux-backend/20261030-085917-b668dfa4/report.json)|59|0|无|
|linux-evidence-11.4.3|[gui](linux-evidence-11.4.3/linux-gui/20261030-085814-17086ea8/report.json)|39|0|无|
|linux-evidence-11.4.3|[integration](linux-evidence-11.4.3/linux-integration/20261030-091345-ccb2c6a0/report.json)|20|0|无|
|linux-evidence-11.4.3|[static](linux-evidence-11.4.3/linux-static/20261030-085719-90e72d82/report.json)|25|0|无|
|m0-report-ubuntu-latest|[static](m0-report-ubuntu-latest/20261030-085531-34838c3e/report.json)|25|0|无|
|m0-report-ubuntu-latest|[gui](m0-report-ubuntu-latest/20261030-085606-197ce25c/report.json)|39|0|无|
|m0-report-windows-latest|[static](m0-report-windows-latest/20261030-085559-fc139df5/report.json)|25|0|无|
|m0-report-windows-latest|[gui](m0-report-windows-latest/20261030-085726-e56c442a/report.json)|39|0|无|

[CI机器收据](ci-evidence.json)、[逐日志与ZIP成员核对](evidence-integrity-audit.json)、[轮次汇总](round-summary.json)。verify helper只用verify模式，未使用collect凭据fallback。通用git_dirty按原报告保留，不擅自推断其具体来源。CI通过不自动关闭Windows全量、实窗观察或科研物理验证。
