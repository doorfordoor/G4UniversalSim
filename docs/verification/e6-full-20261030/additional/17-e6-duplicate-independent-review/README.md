# E6 standard duplicate 不同写者只读审查

结论：对当前`history/run_package_actions.py`的闭合副本核心未发现新增确定缺陷；已知Duplicate & Run当前CLI覆盖问题不计在本核心关闭结果中，等待专用helper落地后另复核。未修改history产品文件、正式测试或修前证据。

## 源码核对

- `_prepare_duplicate:70-83`仅读6个标准输入，拒绝缺失、源文件/祖先symlink；config/macros实际文件集合须与固定集合完全一致，不把未知sidecar默默漏复制。主INI动态场/phase-space/spectrum等非标准键不被当作可移植完整输入；geometry file/copies_file也明确拒绝，未扩K1。
- `:86-93`复用`load_project_snapshot`全envelope/嵌套type/计数/来源选择校验，随后严格要求runPackage所有指向当前源包。adapter可识别旧duplicate pair不等于dup自动修任意矛盾；本helper会明确拒绝而不回读旧包。
- `_ini_entries/_standard_path:36-68`按LF/ASCII空白、保留源级行/注释定位；三个runtime字段materials/file、geometry/config、output/dir各必须唯一，绝对引用须解析到原包对应目标。`:110-113`精确收集三项，`:140-145`只替换三个值，未整文件字符串替换。
- `_snapshot_for_duplicate:175...`所有runPackage路径及pathSettings/geometrySettings相关引用改成新标准包；旧Document路径只作历史来源，专用snapshot入口从当前包实际输入重建，不从这些旧路径读活跃资源。
- 写入使用xb，任意写/close错误向上传播；只有写完6输入并创建空logs/output后返回新目录。部分目录可能保留，但没有成功返回或旧run_status/run_summary继承，不承诺文件系统事务/断电持久化。

## 独立探针

`out/collab/review-e6-duplicate-independent.py`对真实writer含自定义混合材料/edited几何的包执行6组，结果`review.json`、日志`out/collab/e6-duplicate-independent-review.log`：

1. 原包放旧99事件completed摘要及success状态；main保留只含旧路径的注释，并将energy改成6MeV。副本只改3路径，保留当前非路径值和注释；源树SHA完全不变，新logs/output为空；专用snapshot读到的输入全部在新包。
2. materialDocument组分数量用bool冒充int，复用adapter在分配前拒绝，源和目标集合不变。
3. config/geometry新增深层sidecar，闭合资源集合在分配前拒绝。
4. geometry引入file资源字段，明确拒绝，不漏复制外部依赖。
5. 成对旧metadata可被snapshot adapter识别，但duplicate继续严格拒绝不标准runPackage路径；无旧位置读取或假修复。
6. 在最后validation_report写入注入故障（其余输入已写）；函数不返回成功，源SHA不变，无继承run_status/run_summary，history scanner仅得到incomplete。

独立脚本记录产品SHA前后相同。正式`test_duplicate_generated_package.py --component`另执行退出0，16个拒绝例；正式backend版退出0，Inspect及2事件实际运行通过，原源包已移走且原外部材料/几何被改为非法，仍从副本自身成功运行。backend证据在本目录`backend-formal/`，日志`out/collab/e6-duplicate-backend-review.log`。该正式脚本的写者是被审查schema agent，本报告区分独立新增探针与正式回归复跑，不伪称二者同源独立。

## 边界

未操作可见UI，不覆盖未知锁屏缺口；不宣称任意外部INI/任意宏、resource bundle、真实run最终EffectiveConfig或一般物理正确性。UI当前CLI覆盖已由frontend独立实证，root授权窄helper读取副本当前main线程/seed/name；该最后修复本报告尚未判通过，后续补记。
