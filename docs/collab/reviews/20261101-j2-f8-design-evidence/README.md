# J2/F8 历史 DeepSeek 设计咨询原件

日期：2026-11-01。此目录只保存真实设计咨询及咨询前独立 checklist，不是实施验收、CI通过或物理正确性的证据。

请求与response文件完整保留既有调用脚本落盘字节；response.json内raw_response为服务返回的JSON对象，不冒称HTTP原始wire字节。设计正文等于choices[0].message.content加末尾一个LF。原件无鉴权头、密钥、凭据定位或私人绝对路径；接口地址、服务响应ID、usage与模型字段原样保留。

| 原件 | 字节数 | SHA-256 |
|---|---:|---|
| [request.json](raw/request.json) | 6380 | `3b361668bb30de793b6633cb6d7b0b03f110cf1437af9721254a7b7aa2c94bc0` |
| [response.json](raw/response.json) | 10625 | `adae8b6c1d7cb4a06fea71c1642b8a14c6411bad4f44aa1751f7a286f4a1658c` |
| [deepseek-design.md](raw/deepseek-design.md) | 9547 | `75efee09a50983edc32f60e56af285d30d1cc462bbc7f23343aa17ecab3bbdee` |
| [acceptance-checklist.md](raw/acceptance-checklist.md) | 7619 | `9dec23a2aefb6080aee688df987bbcafd7c9eb28e269e58cbb3b2527ea684c12` |

目录级.gitattributes将raw/**设为-text，避免跨平台checkout改变原件哈希。manifest.json给出完整来源、字节身份和排除项。调用脚本含本机凭据定位，故不发布脚本正文；progress.md为临时续接状态，也不作为当前状态文档发布。两者仅保留仓库相对provenance与SHA，原始out文件仍由本机保管。

checklist原件中的复选框属于当时未执行的计划，不能用后续结果回填或据此宣布阶段完成。人工取舍和后续职责仍见原outbox设计回信；本次只是稳定证据落点与链接修复。
