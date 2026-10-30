# F1 第二轮验收后的 GDML 修复提案

基线 `3d1faf1b256a945ac800c08bacf51db57f8ca416`。本提案属于已授权的完整 F1 实现、审查和验收；保持默认输出格式和物理逻辑。

## 判断

1. **确定为缺陷** — `src/Geometry/GdmlInputCapture.cc:140` 的 `FileBuffer` 分配在关闭原生文件句柄的 try/catch 外。确定性分配失败实验复现四次打开、三次关闭。将该分配移入既有保护范围；候选四开四关。
2. **确定为缺陷** — `tools/gdmlInputCaptureCheck.cc:82` 的线程故障路径仅接收 `std::bad_alloc`，不能处理 Xerces 的独立 `OutOfMemoryException`；未捕获线程异常会终止程序。Linux run `41024949824` 的两个版本均在 `effective_gdml` 失败。具体抛出位置不能仅凭 terminate 日志认定。
3. **确定为缺陷** — 同文件 `:78` 的测试用全局文件管理器替换仅在正常路径恢复；异常展开须恢复原指针，不能留下指向已销毁局部对象的指针。
4. **需实验** — Windows Xerces 3.2 的独立构建通过不证明 Linux Xerces 3.3 通过。两个真实 Linux Geant4 版本必须在新冻结提交重新执行。

## 允许修改的文件

- `src/Geometry/GdmlInputCapture.cc`：仅移动分配到现有句柄清理保护范围。
- `tools/gdmlInputCaptureCheck.cc`：线程异常传回调用者，仅具体两种分配失败作为预期拒绝；RAII 恢复测试适配器；新增精确缓冲分配、Xerces 读失败、非分配异常传播及展开恢复检查。
- `AGENTS.md`、`docs/agent-history.md`、`STATUS.md`、`docs/ROADMAP.md`、`CHANGELOG.md` 与本提案：记录修复、失败历史和验收边界。

配置解析、GUI 编辑范围、输出协议和物理计算无改动；本次无需添加配置或 GUI 控件。

## 验收标准

- 原 31 条组件 Check 与 Python wrapper 原断言全部保留；非预期异常必须返回失败，不能 catch-all 后当作通过。
- 同一加强 harness 链接原适配器应复现句柄泄漏；候选精确故障四开四关，Xerces 读失败五开五关，正常与异常路径恢复原适配器。
- 新冻结干净构建，Windows 143 项全量及 E6 同 v3 逐例基线门禁通过。
- 真实 Linux Geant4 11.3.2 / 11.4.3 四 profile 和 M0 Windows / Ubuntu 两 profile 通过，官方产物摘要和全部原始日志证据门禁通过。
- 独立审查通过；实窗仍单独验收。当前 Windows 第二轮 143/143、48,511 断言及 M0 成功不能覆盖 Linux 失败，不能据此关闭 F1。

旧报告原样保留；第三轮使用新目录。实验与补丁记录在 `out/collab/f1-gdml-portability/`，正式归档后由阶段报告链接具体证据。
