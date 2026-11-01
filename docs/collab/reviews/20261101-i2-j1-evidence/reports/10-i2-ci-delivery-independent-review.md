# I2 CI 交付入口独立窄审查（2026-11-01）

结论：发现1项P1、1项P2。仅审源码与小型本地夹具，没有下载数据、构建大包或重复完整flow。审查期间ci_delivery/data bootstrap有继续更新；下列结论针对末版源码，初版“无磁盘预算”的问题已被新增预算/本轮拥有目录清理取代，不作为当前缺陷重复报告。

## [P1] 快照漏掉真正的g4usim_gui.output包，且清单比较也漏掉它

packaging/ci_delivery.py:31、36、56-58：IGNORED把任何层级名为output的目录排除，snapshot_sources拷贝gui时会删除gui/g4usim_gui/output/。original_gui清单也按同一IGNORED过滤，因此双方都缺失还可通过一致性门禁。实际OutputPage/plot_panel在启动时直接import该包（csv_preview/provenance/plot_data等），完整CI从此快照freeze会缺产品代码，最终GUI启动/功能失败；后续freeze封条仅相对已经缺文件的snapshot计算，也无法证明与原完整GUI一致。

确定性小夹具调用原snapshot_sources：源有gui/main.py、gui/g4usim_gui/output/provenance.py及packaging/freeze_identity.py。返回accepted=True、main_present=True、product_output_module_present=False、new_packaging_tool_present=True，证据out/collab/i2-ci-review/source-snapshot-evidence.json。没有执行PyInstaller。

建议按真实生成目录的相对位置过滤，至少不能排除产品Python包；GUI清单比较应对repo-relative路径识别缓存，避免“共同忽略”掩盖缺件。完整packaging目录本身已经复制，新freeze_identity.py没有漏；此P1来自过宽的output过滤，不是缺新包装工具。

## [P2] SDK完整编译日志/冻结审计在CI证据中丢失，部分还先被清理

.github/workflows/full-installation.yml:104-113只上传根json/log、runtime-evidence/sdk-evidence和协调器logs。verify_installation_flow.py:78-87让consumer/application构建发生于acceptance/environments/sdk-{consumer,application}-build；实际configure/build/run.log和sdk-probe-receipt.json由environment_install.py:898、933写在那里，而sdk-evidence只保存引用这些路径的JSON。上传规则没包含实际编译日志，失败收据中的see /.../build.log在runner销毁后不可读。

此外ci_delivery.py:317-319删除source/out/package-build、package-python-build、linux-freeze-work，未先归档freeze.log、binary-sources.json、source-identity.json及封条内容；full-installation workflow也未上传这些目录。desktop-package workflow虽上传自己的相同诊断，它是另一个独立job、另一次freeze，不能代替完整flow的实际证据。建议在owned cleanup前将上述小型日志/收据复制到稳定evidence目录，再上传；SDK只需保留日志/receipt，不必上传巨大对象文件或可执行文件。

## 审查期间已修的入口差异

中间版本曾把--application-build设为缺省False，却无条件读取sdk-application.json；最后复核时ci_delivery.py:104已改default=True并声明完整应用源码构建始终启用，两workflow也显式带flag。该中间问题不列为当前缺陷。

## 当前可确认的正向边界

- full-installation.yml：实际Windows/Linux新runner job，各自SDK/bootstrap/data discovery、原后端构建，调用相同ci_delivery；两平台已明确--application-build，SDK安装consumer与完整bundled backend-source configure/build/run/capabilities两条路径均有实际收据门禁。不是仅检查字符串或仅consumer冒充fullsource。
- ci_delivery snapshot包含packaging/scripts/tools/scenarios/config/schema等并逐文件hash，CMakeCache的实际Geant4_DIR与显式prefix对比；source-snapshot.json保留origin/bytes。除上述产品output包遗漏，未发现因新包装工具未复制导致导入缺件。
- runtime/sdk-evidence两目录已经加入上传，修正了初版只上传顶层/协调日志的不足；但不覆盖上报P2实际build日志位置。
- 末版ci_delivery已记录initial_free_bytes、分阶段space_checks、实际archive/payload预算、可选outer ZIP、canonical data卸载、SDK staging移除及经边界检查的owned中间副本清理，未扩大到输入SDK/仓库之外。先前无峰值预算判断已撤回。标准runner公开规格为14GB SSD，实际可用空间与整阶段峰值仍需真实job记录；不能因本地大盘通过宣称freshhost已通过。[GitHub runner规格](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- desktop-package.yml独立验证真正frozen GUI/Python ROOT helper，并在Linux xvfb/真实VTK actor路径检查外观。它不执行完整Geant4安装/SDK，所以该job绿不能代替full-installation job。

## 新data bootstrap

ci_fetch_geant4_data.py明确SDK先验hash属于caller责任，当前Windows workflow先核对官方SDK实际SHA256再读取其Geant4Config。严格literal描述、dataset/folder/archive版本一致、固定HTTPS源、无凭据/secret代理、HTTPS-only redirects；MD5仅upstream legacy integrity，observed SHA256仅本次实际字节记录，reviewed_artifact=False，未把MD5或观察SHA冒充发布签名。

tar手动逐文件写入，不用extractall：路径拒绝绝对/..、ADS/保留名/尾空白、case冲突与错误顶层；拒绝symlink/hardlink/sparse/special，检查links/reparse及字节/成员限制。末版额外限制PAX/GNU扩展metadata并释放流式TarInfo缓存，没有发现本轮新路径穿越问题。

独立本地无网络小测：实际官方11.4.3 SDK配置解析12项；8种恶意tar（上越、绝对、嵌套上越、错误root、ADS、case collision、symlink、hardlink）均拒绝且无外写，证据i2-ci-review/tar-scope-evidence.json。没有把这些夹具称真实网络下载，也没有称legacy MD5为强来源认证。

## 验收边界

以上为源码/小夹具独审，不是实际Actions run、磁盘峰值、完整安装或双平台freshhost通过证据。P1快照应先修，随后补小型快照回归与证据归档，再由root真实CI闭合；不需要为此次审查重下所有数据或重跑fullflow。

## 2026-11-01 CI P1/P2修复后的独立小夹具复核

结论：以上P1/P2在本轮窄范围均已关闭；原失败与小夹具证据不覆盖。不运行完整CI/fullflow，不将此结论扩张为实际Actions或freshhost通过。

- P1：当前snapshot_sources改为repo-relative生成目录排除（gui/.venv等）及纯缓存名，不再全局排除output；原GUI清单比较使用相对路径，另明确REQUIRED_PRODUCT_PATHS。独立tiny source含output/__init__.py、provenance.py、额外output/extra.py及新packaging/freeze_identity.py、ci_fetch_geant4_data.py，全部真实copy并入hash清单；gui/.venv、test/output仍被排除。源缺少必需provenance时实际拒绝。原source-snapshot-evidence.json的accepted但漏模块失败保留。
- P2：archive_validation_evidence收集本轮freeze log、binary/source审计及封条，真实SDK consumer/application configure/build/run与probe receipt、CMakeCache、实际编译器记录，复制到work/evidence并写逐文件SHA/size/source_stable/index。协调器每stage finally与顶层finally收集失败证据，清理中间副本前另有直接归档调用。现有workflow上传acceptance/evidence/，所以不再只上传指向已丢日志的JSON。
- 小夹具独立创建9个freeze/SDK诊断文件并验证复制后的每个hash；重复调用不增记录，修改application build.log后保留旧内容另增新hash版本，随后仅删除本次临时owned source/out，归档文件全部仍存在。最终10条记录，均可按index读取。SDK对象文件不在上传范围，符合只保留诊断的限制。
- 证据：out/collab/i2-ci-review/ci-fixes-small-review-evidence.json、ci-fixes-small-review.log及review_ci_fixes.py；原venv python -B退出0。第一版探针在Windows用字符串endswith('/...')查找路径而StopIteration，属于探针选择器错误；已保留review_ci_fixes-v1-windows-selector.py，改Path语义后复跑，不把它记作产品失败。
- 新的磁盘预算与owned清理、application fullsource强制门禁等末版语义保留；未实际下载/冻结/编译/安装，runner空间峰值与Actions运行仍由主任务后续真实收据确认。

该复核同步汇总到docs/collab/reviews/20261101-i2-j1-candidate-review.md；不批准阶段关闭。
