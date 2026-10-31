# K1 证据交付包

冻结 `2914b3962167325628ede699b1c14a9d224dec41`。第七本机 Windows 182/0/0、57181 断言，实际父进程正常 exit 0；官方 CI 四 jobs success，12 reports、548/0/0、133720 断言，12 份严格及 F5 同平台逐例/总量门禁通过。

最新证据：[Windows 报告](verification-2914b39/windows/report.json)、[Windows 独审](verification-2914b39/review/k1-seventh-windows-review-audit.md.txt)、[实际父进程退出](verification-2914b39/review/k1-seventh-windows-parent-exit.json)、[CI 审核](verification-2914b39/ci/control/REVIEW.md.txt)、[冻结身份](verification-2914b39/identity/frozen-case-manifest.json)。

I1 在其既定范围内独立完成，见[闭环收据](verification-2914b39/review/k1-resume-i1-closure.md.txt)和[第七身份映射](verification-2914b39/review/k1-resume-i1-seventh-mapping.json)。原生观察保留第四/第五/第六身份，[第七映射](verification-2914b39/review/k1-seventh-native-identity-mapping.md.txt)仅确认产品字节适用性，不声称重新运行全部原生流程。

K1 未阶段关闭。资源边界专项独审未完成，原拒绝不重试；既有反例和 r3 待裁决范围见[原始记录](review-evidence/k1-relocation-candidate/README.md.txt)与[原 incident](review-evidence/incidents/relocation-independent-review-incident.json)。自动化、I1 或普通功能通过均不能覆盖该缺口。[root 主审候选](review-snapshots/k1-seventh-chief-review.md.txt)已按稳定原件加入，独审以另收收据为准。本树未封存更新中的主审草稿或第六检查点。

| 代次 | 归档 |
|---|---|
| 第四 | [原字节归档说明](verification-8213ced/README.md.txt)；[独立追加索引](verification-8213ced-addendum/index.json) |
| 第五 | [原字节归档说明](verification-f9a9ddb/README.md.txt) |
| 第六 | [failed 历史](verification-4167c44/README.md.txt)，保留 cp1252 原失败、native 勘误及真实 external/CLI 补证 |
| 第七 | [归档说明](verification-2914b39/README.md.txt)，当前自动化与各身份映射 |

所有复制的历史 Markdown 均以 `.md.txt` 保存，原始字节与 SHA 不变。历史内部清单、报告绝对路径和链接保留原文；它们记录原位置，不作为干净检出的活动文档。定位时使用 [source→delivery 复制清单](delivery-copy-manifest.json)和[最终目标映射](delivery-target-map.json)。只有本外围 README 是新编写的活动 Markdown。

第六原 visible 两次运行都是 generated；[勘误](verification-4167c44/review/sixth/native-coverage-correction.md.txt)保留。真实 external 补证只接受 01/05 两个不同画面，02/03/04 误标重复图与两次 postcheck 失败原件均留存；不冒 external pending 已完成视觉验证。

历史大包仅用 32MiB transport parts 交付，不放入完整大 ZIP/reassembly 副本。恢复工具只重组 ZIP、不解压、不覆盖文件。例如从本目录运行：

```powershell
python history/transport/restore_evidence.py history/transport/failed-c644bb1/transport.json --output-directory <新的输出目录>
```

小 e5 原 ZIP 保存在 history/ 下。原官方 CI ZIP 字节保持，包括其已有 EXE；没有另加独立 EXE。Windows 深层 case 原件在各代 case-originals.zip 内，成员 SHA 可由原 selection.json 对照，外层改名以复制清单定位。
