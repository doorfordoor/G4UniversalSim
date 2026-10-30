# 核查时间 2026-10-30T09:12:07.3533428Z

Linux 两 job 仍在 Run backend tests on Linux；M0 终态成功且证据已收齐。未重复触发工作流，未有全轮结论。

---

# 最新状态 2026-10-30T09:03:12.618828+00:00

M0终态成功且完整收齐：两原ZIP官方SHA匹配、完整joblogs/terminal元数据、安全解包及4报告严格gate全0。Windows static25/gui39共64项，Ubuntu同64项；m0-precheck.json。Linux两版本仍backend in_progress，尚无integration/全轮结论。

---

# 最新状态 2026-10-30T09:01:37.563030+00:00

M0两job均completed/success，正在收集原始终态/日志/ZIP；Linux11.3和11.4两job均Run backend tests on Linux（in_progress）。未有全轮结论。Ubuntu原ZIP/日志已保存并匹配官方SHA。

---

# 最新状态 2026-10-30T08:57:54.486575+00:00

M0 Ubuntu job123973207657 completed/success；Windows job123973207214 in_progress/Verify tracked source inventory and static tests。Linux11.3 job123973207024、11.4 job123973207198均in_progress/Build the backend。未触发或重跑workflow；尚无全轮通过结论。下一步保存已终态Ubuntu日志，继续有界等待。

---

# 第三冻结CI监测检查点

目标HEAD f176d0ed4cea60b7ca5a80ed81017c9404ec1257，Linux41028779177，M041028779326。严格仅本证据根，不改tracked，不启动主exe/全量/构建/UI，不重跑CI，不使用collect凭据fallback。

初次检查：四job均queued；Linux11.3 job123973207024、11.4 job123973207198；M0Windows123973207214、Ubuntu123973207657。尚无终态通过结论。terminal后保存run/jobs/artifacts、四完整decoded joblogs和四官方ZIP，SHA匹配且安全解包；12报告全部case logs/marker/双指纹及143case冻结集合核对，最后verify模式。

根Windows34506未触碰。下一步有界等待后观察job状态变化；原始终态文件只独占写入或复用同字节，禁止覆盖。


## 最新追加 2026-10-30T09:14:17.9180148Z
Linux job 123973207024 与 123973207198 均 in_progress / Run integration tests on Linux；M0 两 job completed success，4报告 strict gate 通过。全轮尚未终态。


## 最终追加 2026-10-30T09:19:32.381365+00:00
第三冻结 f176d0ed：Linux/M0 两run及4job均 completed/success。4官方ZIP/digest、4完整joblogs、终态run/jobs/artifacts已保存；安全解包12reports；正式verify exit0，12/12 strict gate；414逐case日志SHA与assert marker核对通过，0失败。详见ci-evidence.json、round-summary.json、evidence-integrity-audit.json、verify-invocation-receipt.json、README.md。Windows全量/实窗/物理验证独立，不据此宣告F1关闭。
