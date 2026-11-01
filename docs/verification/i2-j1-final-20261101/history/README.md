# 历史失败证据（保留，不重写）

[原duplicate失败ZIP](raw-evidence.zip) / [清单](manifest.json) 保存ba81615正式GUI的184入口恰一次inspection断言失败；原日志没有case/count/state，后续通过不能改写它。

[已有候选归档身份](prior-archive-reference.json) 指向此前已提交的95件原始审查ZIP及SHA。QtCore/PATH污染、pre-resolve错误归因撤回、freeze复用/junction及较早CI逻辑独审已在该包，本次不重复；实际ba81615 Actions失败日志另见下方补充。最终docs落址后该目录为 ../../../collab/reviews/20261101-i2-j1-evidence/。5fe0a10 Windows M0短路径fixture原失败仍须由正式automated/CI工件保存；本子包的独立实证只解释机制，不能伪称观察到Actions TEMP具体路径。

未解决历史：duplicate间歇失败未复现、未定位；analysis拖动负rect的Qt停放/折叠解释与未成功复现native拖动边界保留。没有以新通过替换旧failed报告。

## 覆盖范围核对与补充

此前95件包确含i2-qt-icu-root-cause.json、i2-qt-dll-inventory.json和freeze/恢复/CI逻辑独审，但没有实际ba81615 Actions失败job日志。因此本目录另收 [旧CI失败ZIP](old-ci-failures.zip)：4份当时job日志、最新当时run元数据，以及xcb真实冻结诊断artifact原ZIP、缺库映射/说明和本机ldd对照。manifest逐件注明archive_file。它们保留checkout长路径、doc_links、xcb及早期SDK host-tool错误的原现场，不重复95件中的QtCore原件。
