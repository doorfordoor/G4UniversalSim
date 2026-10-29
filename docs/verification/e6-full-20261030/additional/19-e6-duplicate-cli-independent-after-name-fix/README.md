# Duplicate & Run 最后runName窄修不同写者关闭复核

结论：**原P2尾NBSP的最终CLI名字漂移已独立关闭，当前本scope可冻结。**

- 当前唯一产品窄修为`widgets/project_page.py:146` runName `.strip(" \\t\\r\\n\\v\\f")`，使用与INI一致的ASCII空白集合；没有修改路径或其他文本读取规则。
- 复核复制原`out/collab/review-e6-duplicate-cli-independent.py`的原始字节，仅替换OUT输出目录字符串；8个payload、实际检查/Run回调、断言和观测逻辑完全相同。原修前`review.json`和issues保留。
- 新脚本exit0，8例、issues=0。`精确名字<U+00A0>`从helper到inspection及最终Runner `--run-name`完整保留，`expected_name_preserved=true`。
- 缺seed、0/-0、非法seed、GUI1025线程、后端线程0、缺name原7例继续符合预期；缺seed/缺name不继承current7/999/旧name，拒绝状态不变。
- `review.json`记录受检4产品文件SHA前后相同。真实Run入口和inspection完成回调经过产品代码，但QProcess/runner启动拦截、plan合成，不将此作为后端物理或实窗验收。

日志：`out/collab/e6-duplicate-cli-independent-after-name-fix-pass.log`。本轮无产品或正式测试改动、无运行中会话。只关闭root已裁决的同路径范围，不再扩项；最终全量/CI/可见窗口仍以主任务证据为准。
