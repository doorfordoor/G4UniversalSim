# 冻结身份与复用清理窄独审（2026-11-01，J1实现者独立审查未参与实现代码）

结论：原reuse两项P2已修；新增1项P2输出根联接逃逸。仅源码/小夹具与现有单测，未真实freeze、下载或操作实际发布包。J1自身由另一agent复审，本审不替代。

## [P2] clean_output_directory接受out指向检出内源码目录的联接

packaging/build_package.py:137-146先resolve(ROOT/out)再将它视为允许根，仅要求该根仍在ROOT内。未拒绝out本身或祖先是Windows junction/reparse。若checkout/out联接到checkout/keep-source，传入checkout/out/valuable会resolve到checkout/keep-source/valuable；allowed.is_relative_to(ROOT)和target.is_relative_to(allowed)均为True，最终path本身不是symlink，函数调用rmtree，实际会清理out名义范围之外的源码目录。

独立Windows临时夹具在同一私有temp tree创建linked-checkout/out→linked-checkout/keep-source junction，patch rmtree为Mock拦截（没有实际删除）；实际结果rejected=false/would_call_rmtree=true/resolved_target=linked-checkout\\keep-source\\valuable。证据out/collab/i2-freeze-identity-path-review-evidence.json；脚本review_i2_freeze_paths.py。保留fixture源文件存在断言。

建议在resolve前拒绝ROOT/out与目标路径之间的symlink/junction/reparse组件，再执行当前canonical范围检查；Windows不能只用Path.is_symlink，Python3.11 junction需lstat reparse属性。补out根联接指向checkout内非out目录的负例，拒绝前rmtree调用必须为0。正常当前checkout/out未被本审修改。

## 原两P2复核通过

- build_package.main:366-377在任何cleanup前对所有reuse先reject_overlap并verify。changing只含本次将变更的package以及真正重新构建的work/helper_work；reuse的标准OUT/package-build/dist路径不再加入被清理work。420-424仅在非reuse GUI分支clean_output_directory(work)，否则直接copytree；因此原默认复用源不会因复用分支被清理。
- freeze_identity.seal在实际frozen目录写g4usim-freeze.json，绑定kind/platform/3Dprofile、当前源码各文件SHA，以及实际payload逐文件size/SHA。verify比较当前源码、协议和完整payload map，缺收据/旧源码/改payload拒绝。
- build_package复制GUI/helper后再次verify目标目录，所需当前source与实际复制字节均再核对。独立小夹具真实copytree后verify通过；复制目标篡改后verify拒绝。standard reuse源在夹具中保持存在。不是只凭self-test的9页就视为源码身份相同。
- test_frozen_startup.py实际独立原venv v3退出0、G4USIM_ASSERTS=16，日志i2-freeze-identity-independent-test.log；覆盖旧源码/篡改payload/overlap/outside-out普通路径、非交互Qt import失败、旧报告不覆盖、DLL来源拒绝。该单测未覆盖本次out根联接逃逸，不能用它的绿色覆盖上述反例。

收据是本地源码/字节一致性证据，不是第三方签名或来源真实性证明；本审未改变其既有证据范围。root修复新增P2后需窄复核，本审未修改packaging产品或正式测试。

## 2026-11-01 P2关闭复核：输出根与中间联接

结论：本报告新增out-root junction P2已关闭。主负责人修复clean_output_directory后，本审未修改packaging产品；获临时独占授权仅补scripts/test_frozen_startup.py永久回归。

- 源码确认：resolve前逐lexical ancestor lstat拒绝symlink/reparse（含Windows junction），覆盖ROOT/out；canonical allowed必须恰为ROOT.resolve()/out，target必须strict descendant。
- 原私有Windows反例复跑：rejected=true、would_call_rmtree=false、source_still_present=true，复制后验/篡改拒绝/标准reuse源保留仍通过。新证据i2-freeze-identity-path-review-fixed-evidence.json与i2-freeze-identity-path-fixed.log；原失败证据保持。
- 永久测试新增output-root-alias→checkout内非out keep-source，以及out/stage/alias→out/retained-cache的中间联接。两例rmtree Mock调用必须0，marker字节必须原样。另真实普通out/cache递归清理成功、out根保留；所有夹具位于本次私有temp tree，执行实际正常清理前已验证resolved目标包含关系。
- Windows原venv执行tools/test_assert_probe.py scripts/test_frozen_startup.py：exit0、G4USIM_ASSERTS=33，i2-freeze-cleanup-alias-regression.log。junction以普通mklink /J创建，无权限提升。
- 现有WSL python3/POSIX symlink执行同一正式脚本：exit0、G4USIM_ASSERTS=31，i2-freeze-cleanup-alias-posix.log；未安装或提权。
- 未真实freeze、下载或清理实际发布产物。本结论限该P2及原reuse窄契约，不扩张为完整I2阶段关闭。
