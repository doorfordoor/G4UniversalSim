# E6 generated-run helper与最终GUI命令不同写者复核

本轮只读，源包/正式测试/产品文件未改；`review.json`记录4个受检产品SHA前后相同。独立脚本`out/collab/review-e6-duplicate-cli-independent.py`在新目录执行8例，实际经过Duplicate & Run→输入检查→检查完成回调→Runner命令构造；QProcess和runner启动被截获，检查回包是明确的合成合法plan，不宣称真实后端或可见窗口运行。

## 已关闭范围

- `history/run_package_actions.py:43-65`：完整ASCII十进制，符号/前导零按后端strtoll(base10)含义；先去前导零并做十位边界再int，避免Python巨大数字转换上限。threads为1..INT_MAX；seed为0..INT_MAX，-0=0；缺seed=None，显式空/非法/负数/溢出拒绝。与后端`ConfigValue.cc::ParseStrictInt`及SimulationManager负seed拒绝一致。
- `:68-75`只从经完整闭合包校验的当前main.ini读取三项，不采用snapshot旧镜像；只读无分配。duplicate准备阶段调用同一规则，后端非法参数拒绝时不产生新包。
- `window/project.py:263-296`在copy候选上填本包threads/seed/name，对seed使用None判断；新副本读回值才作命令依据。先guard再发布，正常数值2/缺seed/0/-0均不继承当前7/999；GUI threads1025在guard拒绝，非法seed和threads0在helper拒绝，均没有检查/运行启动且当前对象、路径、控件、包状态不变。
- 缺name返回空，最终CLI无--run-name，不继承current。普通复制与复制并运行正式smoke覆盖其他标准case，独立脚本本轮主要观察实际Run回调。

上述数值语义和当前参数污染修复可以关闭，不需扩F1/K1/J2。

## [P2] 同路径run name边界，待root裁决

helper的公开契约与正式底层正例明确保留Unicode文本/尾NBSP。当前main `name = 精确名字<U+00A0>`：

- helper正确返回`精确名字<U+00A0>`；源包字节不变。
- `widgets/project_page.py:146`的`self.run_name.text().strip()`使用Unicode strip；`_set_project`末尾build_command_preview和实际检查回调都会经过它。
- 独立最终Runner命令含`--run-name 精确名字`，比本包main少尾NBSP，因CLI优先级会覆盖该原名。`review.json::issues`与日志保存原值/实际值；其他7例未发现问题。

这不改变物理参数，属于run label精确保留的P2，不夸大为数值污染仍未修复。若保留helper/API的既定尾NBSP承诺，最小同路径修正是Project页run_name按与INI一致的ASCII空白策略读取，或明确阻止无法准确呈现/传递的名字；不能只修改测试把差异当同值。是否作为冻结阻断由root按本轮已定范围裁决，本agent未改前端。

当前结论不是全阶段完成；未知锁屏可见窗口、最终全量/CI与基线门禁仍另行验收。
