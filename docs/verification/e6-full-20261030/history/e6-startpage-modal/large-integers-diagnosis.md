# E6 项目导入整数范围与发布失败污染（冻结只读复现）

结论：**确定缺陷，P1**。`load_project` 现只校验整数类型，未保证现有GUI控件可准确表示；`window/project.py:54` 在页面设置前发布`self.project`，`:146`的`_set_project`调用位于load异常捕获之外。于是后续Qt赋值异常会穿出，且已改变当前项目/部分页面/运行包状态。

## 实际观察

独立offscreen脚本`review_large_integers.py`退出0，11个case全部保留源文件字节，产品文件哈希前后相同。结构化证据`large-integers.json`，完整日志`large-integers.log`。

| 输入 | 实际结果 |
| --- | --- |
| flat threads = 10**100 | 读项目成功；`project_page.py:128`抛OverflowError；旧项目对象未保留，项目名控件已写入incoming，Project页`_building=True`，旧`project_file`仍指旧文件 |
| runSettings.threads / beam_on = 10**100 | 读项目成功；`config_builder_page.py:198/:200`抛OverflowError，旧对象已替换，Config页`_building=True` |
| scoringSettings.hist_bins = 10**100 | `config_builder_page.py:222`溢出，状态同上 |
| scoringEditor.hist_bins / trajectory_events、sourceEditor.preview_ray_count / random_seed_preview = 10**100 | `widgets/config/run_config.py:372/:369/:355/:356`溢出，旧项目未保留；Config页至少已部分更新 |
| flat threads = 2048 | helper返回True；QSpinBox上限1024，最终模型与控件都成1024，源JSON仍为2048，导入时被静默改值 |
| runSettings.beam_on = 2,000,000,001 | helper返回True，模型值仍2,000,000,001但控件成2,000,000,000，页面/模型不一致 |
| scoringEditor.hist_bins = 10,000,001 | helper返回True，模型仍10,000,001但控件成10,000,000 |

八个巨整数case均观察到：`generated_package_stale`由人为设定的False变True，`generated_package_dir`从sentinel变空；异常后当前项目对象不再是旧对象。无QMessageBox被触发，因为异常在现有try之外。不是Windows锁屏或offscreen模态造成的结果。

## 建议同轮修复范围

与已定位的modal严重级别修复同轮处理，但等待原冻结证据封存后再改。本轮未修改产品或正式测试。

1. 在`_set_project`任何发布、页面赋值或信号反馈前检查现有编辑器所有QSpinBox字段（含flat/runSettings/ScoringSettings/Editor/preview字段）的可表示范围；可从实际控件min/max取范围，错误包含项目字段路径，明确拒绝，不能限幅“修复”。这是GUI项目表示边界，不扩物理支持。
2. 普通Open critical、近期/快照warning均必须保留实际错误和旧对象/路径/页面/陈旧标记。仅把`_set_project`包进except然后返回False不足以回滚已污染状态；至少上述可预测投影错误须在发布前完成检查。
3. 新smoke保留这八个巨整数和三个静默限幅反例，分别断言拒绝、错误文本、旧项目对象和全部关键UI状态不变、`_building`仍False；原文件字节不变。

本问题与已关闭的JSON类型P1/P2不同：输入是合法JSON整数，但GUI无法准确表示。原类型修复仍成立，不能用该关闭结果代替本数值范围/事务路径验证。
