# K1 P1 永久防回归补充：冻结前探索结果

当前仅正式文件 `scripts/test_k1_staging_alias.py` 被修改，新增73行、删除0行；产品未改，未commit/push。待root及独审看完并提交该测试，再生成clean提交绑定的规范单例报告。

最终测试 SHA256：`0d5cb4db40d50417e16a316ec8825ddd30c7265a0b8d468679529288e9a95de2`。
当前产品 experiment_bundle.py SHA256：`5c1dff0338e80a673ba8f3427aeb7bfe1abe9d2b5315efca564310be8118385a`。
HEAD：`e93072867021ae1978a7de3834c51caf0f9fb839`。精确diff见 `test-change.diff`，其与当前 git diff 一致；`git diff --check`通过。

新增 late_receipt_link 确定性地在真实 inspect 完整核验返回后、export最终收据复核前，把独占external-source改名并替换为指向本次staging/resources的目录链接。Windows为真实NTFS junction，POSIX为真实symlink。所有路径先核定属于当前case根；finally仅删除链接本身、恢复原源目录，断言源前后SHA一致。行为判据必须拒绝、不能发布、staging消失。旧exercise全部原语句顺序保持，原17个assert AST全部保留，现39个AST；不把入口计数当独立命题数。

| 探索运行 | 退出 | v3入口 | 行为 |
| --- | ---: | ---: | --- |
| Windows当前产品+新正式测试 | 0 | 36 | 原全部正常/静态链接/8.3检查及新增晚变化拒绝通过 |
| WSL Ubuntu当前产品+新正式测试，Linux本地/tmp夹具 | 0 | 33 | 原正常/静态symlink及新增晚变化拒绝通过 |
| Windows旧r2仅进程内加载+完全相同新正式测试 | 1 | 33 | 在新增第90行“必须拒绝”断言失败，收据error=null/published=true；源恢复通过 |

反向对照是真正测试失败，不是把预期错误发布写成pass。旧r2产品SHA `34db09d96260841411dc92306f4eab438d75792a4f74abacde3322c10b3d66c2`。完整原始日志及落盘SHA、命令见 `exploratory-complete-receipt.json`。初次部分运行收据 `exploratory-receipt.json` 保留。

Windows解释器为CPython3.11.9；WSL解释器 `/home/u123/venvs/g4-f4-qt-6.11.1-20261030/bin/python`，CPython3.11.18、PySide6 6.11.1。此用例不启动Geant4；只测这一个Linux Python/Qt平台，不称双Geant4版本。

## WSL文件系统限制与证据

首次WSL把fixture放在/mnt/c（Windows挂载盘），在原control导出、进入新增反例前，既有 `_publish_directory` 的renameat2返回EINVAL（exit1、0入口）。该失败完整保留在 `wsl-linux-current.log`，不能冒充新增case通过。未改产品以适配挂载盘。

随后同一新正式脚本在Linux本地 `/tmp/k1-p1-permanent-regression-20261031-tw_to3_p/evidence` 成功运行。该目录由tempfile独占创建，原件保留；全部文件逐SHA复制到 `wsl-linux-ext4-current-evidence`。运行平台与复制SHA清单见 `wsl-runtime.json`。规范runner也应将WSL report-root置于Linux本地文件系统，完成后逐SHA复制完整报告到本证据根的新子目录，门禁需对原件和复制件分别运行，不能在DrvFS中创建发布fixture。

## 待root冻结后的规范验证

root提交单一正式测试并由独审通过后，在全新子目录分别执行：

`scripts/run_m0_tests.py --profile static --case k1_staging_alias --report-root <new-native-root> --require-tracked-sources --fail-on-skip`

接着使用 `scripts/check_report_evidence.py --report-root <new-native-root>` 严格核验，不用allow-incomplete，不把旧全矩阵裁剪为单例baseline。现有dirty探索收据不覆盖。规范报告需绑定实际clean提交，保持产品SHA、测试SHA和本次负对照身份映射。

当前没有运行会话；正式报告尚未跑，等待root提交通知。
