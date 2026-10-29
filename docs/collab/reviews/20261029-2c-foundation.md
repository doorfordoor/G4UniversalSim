# 2C foundation

HEAD f25da40，基础层独占范围：EffectiveConfig、IniReader、InputProvenance及独立测试。保持schema v1；无Geant4构建。

API：Registry::Commit(fields, erasedPaths={})、ReplaceModule(module, fields)。空/相同事务不增revision，失败候选不发布；删除与写入同路径拒绝；完整模块替换清除模式切换残留。Snapshot按值不可变。InputProvenance ReadFile(path)一次binary读取返回path/bytes/sha256；Sha256(bytes)无外部库。IniReader原子Load，GetDeclarations保留按文件顺序的所有键（含重复），GetInputSha256返回实际解析字节指纹；GetFields/消费追踪保持旧行为。

风险与边界：文件hash证明实际读取内容，不证明之后文件未变；解析消费者必须使用返回bytes，不能重开计算。revision仍为字段事务语义，不是Git/物理成功；快照Capture本身不改revision。消费重复声明链只读不改变consumed。

## 实现与独立验收

基础层完成，可供集成。最终API：
- Registry::Commit(std::vector<Field>, const std::vector<std::string>& erasedPaths = {})，输入revision不采信，未变字段保留revision；重复删除/删除+写入同path拒绝，失败不污染候选。
- Registry::ReplaceModule(const std::string& module, std::vector<Field>)；module使用未转义名称，内部JSON Pointer首段精确匹配，空替换清除。Capture不改revision；同内容重复commit不增revision，相同应用证据省略applied_revision时保留旧应用revision。
- input_provenance::InputFile {path,bytes,sha256}，ReadFile(const std::string&)一次binary读取；Sha256(std::string_view) exact bytes SHA256，无Geant4/第三方依赖。root须在目标加入src/Config/InputProvenance.cc。
- IniReader::GetInputSha256() const -> const std::string&；GetDeclarations() const -> std::vector<IniFieldInfo>按源顺序含全部覆盖声明；GetSectionDeclarations() const -> std::vector<IniSectionInfo>含所有显式头。IniFieldInfo末尾追加rawLine；旧GetFields仍仅获胜声明/原消费行为，历史只读取出不消费。Load完整解析候选后swap，缺文件/目录/坏语法不改旧字段、消费、文件名、历史或hash。

测试：scripts/test_effective_config_model.py扩展模块切换删除、相似前缀隔离、空与相同事务、重复冲突/非法候选原子失败、不可变旧快照、应用证据幂等；新scripts/test_input_provenance.py独立编译IniReader/InputProvenance/StringUtils，SHA官方已知向量与hashlib padding边界、中文路径、CRLF exact bytes、重复键/section顺序、原文、消费隔离、后改磁盘不改变已接受输入hash、失败Load保留、成功reload清旧历史。两项exit0，v3Python入口分别18/15；C++运行内含多项require检查，入口计数不是其数量。证据out/verification/2c-foundation/{effective-model,input-provenance}.log，git diff --check通过。未构建Geant4、未修改CMake/Manager/main/runner；尚待root真实解析器与生命周期集成，不称完整2C已完成。

## Source / Physics / Field 消费者接线（进行中）

1959完整开工信已读。现扩展独占include/src Source、Physics、Field和Scoring/PhaseSpace；root接管EffectiveConfig.hh/.cc、所有生命周期和其余Scoring。Origin.disposition已添加并交还root。IniReader::LoadBytes(path,bytes)已提供，原子解析与hash同输入复用；新增virtual路径/失败原子性回归。

三Manager统一API：ExportEffectiveConfigFields() const -> vector<Field>；ExportEffectiveConfigEvidence() const -> Value(Array)；ConfirmEffectiveConfigMutation(const string& command,const Origin&)（仅root确认真实成功后调用）。Source逐SourceSpec按适用模式投影；legacy用/source/<field>，具名保留原section配置名及JSON Pointer转义；phase-space模式仅文件顺序/sha256/历史/粒子/recycle，不混GPS旧字段。七类能量按实际成员投影，uniform/power/exp/histogram/points不输出unused mono；位置shape/presence/角分布flags、离子/rest与preset/重复键链。谱、相空间、场图均ReadFile一次bytes解析，hash不在导出时重开；PhaseSpace::ReadHistories(files, vector<InputFile>* acceptedInputs=nullptr)成功末尾发布path/hash元信息，bytes释放避免重复持有全部输入。

共享头文件Config/EffectiveConfigSupport.hh：ConsumerState包含accepted字段/reader/generation、深Clone（配置副本、空收据）、Accept(reader,fields)、Make(path,value,unit,section,keys)、Confirm(fields,command,origin,unknown=false,targetPaths={})。同值命令需显式targetPaths，Source/Physics已按命令识别作用域。默认requested保持unknown。Record在实际receipt附generation及匹配配置字段resolved_sha256；Evidence只读拷贝；mutex保护多线程收据。EffectiveRuntime.hh的Receipt采用run_id/thread_id/role/application_status/evidence_level/evidence_source/observed/stage/path/reason。

运行点：Source GPS Apply与每次Prepare实际只读GPS粒子/能量类型/mono值/位置回读，离子未准备前不冒称应用；原生GPS确认后application unknown，读回也不冒充Manager值。FieldSetup只在真实Construct（非Validate）记录transport/global与每LV真实field manager绑定；不会把master预检当worker。PhysicsList实际ConstructProcess后观察粒子真实process表，SetCuts后读defaultCut；Factory仅记录真实registered constructors，不冒充process已构造。公开PhysicsManager::ObserveEffectiveConfigPhysics(const G4VModularPhysicsList&, const string& stage) const供root在reference list初始化后/真实worker节点调用，stage=physics_process才读取实际process表；reference现有factory注册收据不足以宣称线程process构造。region实际G4Region/cut/user-limit证据仍由root几何路径提供。

验证：七个消费者.cc通过g++ C++17 -fsyntax-only（不链接/不生成Geant4二进制）；新独立test_effective_consumer_state.py验证重复来源、请求unknown、同值目标来源、深clone隔离、unknown及收据指纹，exit0（Python v3入口3，C++内含require）。test_input_provenance含LoadBytes新增反例exit0。新的test_effective_source_physics.py为真实后端专项，覆盖全部能量模式/具名/相空间/离子/位置角度/physics region/场图hash，已py_compile，等待root统一新构建后执行；未拿旧exe冒充新实现。尚未完成整阶段验收。
