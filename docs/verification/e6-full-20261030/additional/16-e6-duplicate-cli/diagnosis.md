# 标准运行包复制后的 CLI 覆盖复现（只读）

**确定缺陷。** `window/project.py::duplicate_history_package`仅换config/macro/output，保留当前project的threads/seed/runName；`runner.py:125-129`始终把这些字段写成显式CLI覆盖。

实际`create_run_package`生成标准包：main `threads=2, seed=43, name=writer_run`。当前UI设为`threads=7, seed=999, runName=unrelated_current_run`，执行真实`duplicate_history_package(run_after=True)`，仅在`inspect_external_macro`处记录将使用的真实`runner.build_command`，**没有启动inspect/backend进程**。

结果：副本main仍为2/43/writer_run，而命令包含`--threads 7 --seed 999 --run-name unrelated_current_run`。source snapshot flat字段更是1/空/空，不能拿可能陈旧的flat snapshot作补丁依据。结构化记录`review.json`；复现脚本`review_duplicate_cli.py`。真实QProcess状态均NotRunning。

## 等root批准的最小方案

1. schema写者把已有`history/run_package_actions.py::_ini_entries`严格ASCII/LF scanner封装成标准generated包的窄helper，读取**新副本已验证main**的`[run]/threads, seed, name`。只支持已验证标准包，不建立任意主INI反向导入器。
2. helper区分缺省seed（清空CLI seed，不能继承当前999）、显式0、合法有符号整数；threads/name的缺失/默认政策按标准writer/后端现契约明确，不用snapshot猜。重复、非法词法/范围等须有文件/字段上下文。优先在分配目标前作同一验证，避免新复制包文件已落盘后才发现坏参数；前端仍以新副本读取结果为准。
3. 前端候选copy：新config/macro/output、external；只对齐flat及runSettings的threads/seed/run_name镜像，保留其他UI设置；先投影preflight，再`_set_project`发布及更新包视图，最后可走原Inspect→Run。失败保留旧项目/路径/widgets/package状态。snapshot恢复路径不改。
4. 新GUI回归用真实writer、当前UI7/999对包2/43，截获命令，覆盖复制但不运行和复制后准备运行；还需将main run三字段手工改为与snapshot记录不同，证明采用当前已验证main；覆盖seed0/省略、坏语法/越界拒绝与原状态完整保留。不执行后端属于命令证据；实际执行沿用root的复制端到端回归另证明。

本轮产品/正式测试未改，待root确认及schema helper接口。
