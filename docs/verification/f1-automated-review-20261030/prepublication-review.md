# F1 自动归档计划独立复核

结论：**APPROVE（仅批准自动证据归档计划）**。未发现阻断项。实窗仍 pending、phase_complete=false，不批准关闭 F1 或声称物理验证通过。本次未发布目标目录。

## 复核对象与执行

- 产品冻结：f176d0ed4cea60b7ca5a80ed81017c9404ec1257。
- 计划：f1-automated-archive-plan.json，SHA256 `a5d05c536c31899529cdc4a78d7738693dc1a0e326f3b4eb521e0e349d57ae8a`。
- helper 实际文件 SHA256 `c164beaa0cfe9026224acda6ca00c4257574f4d9caf85d9dc96fa5d2060aad0c`，与指定候选一致。
- 已执行 `python out/collab/archive-f1.py --review-plan out/collab/f1-automated-archive-plan.json --review-output out/collab/f1-automated-plan-independent-gates.json`，原会话21832最终 exit0。收据 status=review_passed_not_published、archive_published=false；2797源文件逐字节校验；目标 docs/verification/f1-automated-20261030 仍不存在。

## 分类、严格门禁与历史真实性

临时复制后的36份报告分别为最终Windows1、最终CI12、历史CI20、历史Windows2、E6基线1。最终13份均strict exit0；Windows143/143、48511断言，基线比较exit0；CI官方artifact→profile拓扑4/12无重复缺失，run/job/head关联及入档报告路径集一致。最终CI414次执行、143种冻结用例，不能混称414种测试。

历史首轮4份gui报告及1份Windows报告仍strict exit1，第二轮2份Linux integration仍strict exit1；共7份原失败报告被保留并明确不计最终验收。历史成功报告也仅归history/baseline，不伪装为当前冻结。计划的historical_rounds保留cd0f44a与3d1faf1真实HEAD、原官方ZIP摘要和失败状态。没有追改原始日志、报告或旧README。

首轮三份补收日志receipt及原字节逐项复核通过：job123949508758、123949508802、123949508743的size/SHA均匹配。旧M0 Ubuntu job123949509175只保留presence-only边界；README明确纠正“先前四份已落盘”的错误，未把补收日期伪装为首轮采集时间。

性能54+18个sample分别来自原格式/缓冲测量，计划重新核对原INI/macro/log SHA；不拿已被后续exe覆盖的路径重算历史程序身份，不称最终冻结重复性能测量。16份独立review以原字节.md.txt保留历史解释边界。DeepSeek设计收据与响应单独分类：response ID 65103662-33be-422d-b21a-4b1f876b9e51，prompt452/completion1268/total1720，实际调用与建议采纳/纠偏分开；不是实窗或物理证据。

## 冻结身份与真实夹具

最终build receipt、Windows/CI报告、fixture receipt及README的源码指纹均为 `db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc`，测试指纹均为 `57a80e4f5e73a2d07b5b834b6ca91ac482161622ca1d5e1d558cbd37d79b5f35`。实际读取当前exe重新SHA得到 `f02d3bdc94121dcf35de05e152773fdec8c87f5c8759e53fd1f95d3f51f43ea8`，与build/fixture/README一致。

最终真实fixture单独归visible/1-f1-visible-gdml，仅表示后端小运行：2workers、2run各2/2、auto→root、20登记文件身份verified。其receipt明确window_started=false、visible_observation=pending、desktop_operations=false、close_file_control=false。ROOT/ZIP/exe大文件未入档，计划excluded保留本机源位置；README明确不是独立可移植实验包。

## Linux GDML 原日志直接核对

实际读取本轮两份effective_gdml.log，而非只引用报告pass：

|版本|原日志SHA256|实际内容|
|---|---|---|
|11.3.2|aa0adf676a2c55994787089facc430b89462f5e3b185cd94a3a4427757b90410|FAULT FileBuffer opens=4 closes=4 refused=1；PASS allocation fault checks opens=5 closes=5 adapter_restored=true；PASS native capture；G4USIM_ASSERTS=11|
|11.4.3|d9b78ff6b2d760417148785d684bff1c0701a8929a4d14a14f5f6f55a0f53200|相同四开四关、五开五关、adapter恢复、native capture及11断言标记|

两日志SHA均与各自integration report的effective_gdml记录一致，记录exit0/pass。原日志还包含四个实际输入SHA、HTTP schema捕获、未到EOF partial明确UNKNOWN；没有把失败/不完整读取伪造完整hash。

## 链接与完成边界

临时布局的3份活动Markdown、23个本地链接全部可解析，broken=0；历史Markdown作为字面.md.txt保存原字节，不拿原out路径存在性假装归档链接可携带。外链/anchors不在此检查的真实性范围内。后续发布仍需对源SHA再验并独占发布。

f1-delivery-state.json明确automated_validation=passed、visible_acceptance=pending、phase_complete=false、integrated_to_codex=false；README首段及后文一致。后续文档提交不能冒称已测exe构建提交，实窗需另建证据且不得追改本自动报告。本复核仅新增自身报告及临时review门禁收据，没有改被计划选中的任何原件。
