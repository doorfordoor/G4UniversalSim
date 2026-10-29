# 完整 2C：材料、几何、偏置消费者设计检查点

2026-10-29；实现 root `C:/Users/123/.codex/worktrees/effective-config/G4UniversalSim`，只读基线 HEAD `f25da40fff1786781c597063dd41924552448cfb`，开始时工作树干净。本阶段仅新增本设计记录，不构建、不改源码，等待 root 确认公共 adapter/InputProvenance 契约。

已读仓库 AGENTS 的 2C、A5、材料闭合 schema、Q1 生命周期相关约束，agent-history 的 configured 子集条目，EffectiveConfig.md 完整 11 消费者表及 source 接入要求，20261029-1010 开工信。旧 configured 子集不提升成完整消费者覆盖；导出不得调用 getter 以外的构造/消费追踪接口或隐式初始化 Geant4。

## 建议公共只读 adapter 契约（待 root 统一）

沿用 effective_config::Field / Origin / Value，避免各模块自行拼 JSON。每 Manager 提供 `std::vector<effective_config::Field> ExportEffectiveConfigFields() const`，一次取得一致副本；只投影实际接受的配置记录，不调用 getter 触发 NIST 创建或 consumed 标记。来源记录与配置接受事务共存，导出不从当前缓存倒推原请求。

应用证据另提供 `ExportEffectiveConfigEvidence() const`（返回公共 EvidenceRecord 值类型，名字待确认），不得直接覆写共享 registry。建议 EvidenceRecord 含 path/object_id、configuration_generation、stage、run_id/thread_id（只作证据 scope，不能组成对象 ID）、level/status、observed_value、source/reason。root 在 Configure/RunBegin/finalization 收集并统一提交；旧 generation 的构造/worker 收据不能赋给新 revision。失败本身另为失败事实，不能把成功字段改为伪失败值。

成功命令来源由 root 在已确认 ApplyCommand 与各 Messenger 错误计数均成功后通知，例如 `ConfirmEffectiveConfigMutation(command, Origin)`；模块 setter 只能留下实际成功变更的 pending delta，不能在进入 Messenger 时先提交宏来源。失败命令清除 pending 但保留实际已发生的部分对象失败事实。无来源的直接 C++ setter 标 runtime_unattributed，不捏造 macro/INI。

Registry 公共层需确认模块 replace/remove 和事务 generation：几何换模板/材料定义替换/bias Clear 后不能残留旧字段；requested_known=false 与显式 null 分开。完整覆盖链按实际输入顺序保留默认、别名/重复声明、显式覆盖，不能只拿获胜字段 GetFields。模块 off/auto/on 请求及解析 reason 也用字段投影；geometry/material 是基础依赖，不能关闭后成功。bias auto 只在显式完整规则与有效挂接条件下启用，mode 缺失维持旧布尔语义；冲突必须拒绝。

## 实际读取点与文件范围

| 消费者 | 当前真实入口及问题 | 实施计划/证据边界 |
| --- | --- | --- |
| 材料 INI | MaterialIniReader.cc:106 打开文件，Load→ParseSections 形成定义；MaterialManager.cc:52 LoadMaterials 在 BuildAll 后才记 loadedConfigFiles。reader SourceInfo 当前为私有局部来源且重复声明被 map 覆盖。 | reader 从公共 InputSnapshot 的同一 bytes 解析并保留声明历史；成功定义与来源一起移入 Manager。BuildAll 可部分成功后抛异常，现有 incompleteConfigLoad 必须保留，不允许把整次失败 load 当成功 provenance/revision。 |
| 几何 hierarchical INI | GeometryConfig.cc:86 独立 ifstream，137–138 又用 IniReader 重读；GeometryConfigDiagnostic.cc:101、133 再读重复/大小写声明。 | 必须统一同一 InputSnapshot，并让值/来源/diagnostics 共享 bytes；不能把第2次读取哈希贴给第1次解析值。保留现有警告/后值语义。 |
| 其他几何模板 | GeometryManager.cc:223→TemplateFactory→BuildNodesFromFile；真正模板实现位于 src/Templates，非已授予的 Materials/Geometry/Biasing 目录。 | 请求 root 授权必要 include/src Templates 文件，或由 root 修改其公共 BuildNodesFromFile 入口向下传 snapshot。禁止为取来源再次解析文件。 |
| STL | StlReader.cc:72–77 binary 读取完整 data，随后 ASCII/Binary 均从该字符串解析。 | 直接用相同 data 的 SHA；保存长度、格式、lengthUnit、facet 数及引用来源。只在实际成功读入后记 accepted；configure 未读到时明确 pending。 |
| 几何辅助数表 | GeometryConfig.cc:860 还有外部 path 的 ifstream（轮廓/顶点数据路径）；不仅是主 geometry.ini。 | 将该输入也接 InputSnapshot，记录引用字段、顺序、实际字节哈希与解析单位，不遗漏辅助文件。实施前逐分支列清精确消费字段。 |
| GDML | GdmlIO.cc:27–35→G4GDMLParser::Read(path,validate)；本地 G4GDMLParser.hh:68/74 仅 filename Read/ReadModule，G4GDMLRead::Read 非 virtual filename API。原生可能继续读模块、schema、外部实体。 | 配置阶段只能证明 descriptor 请求和路径，不能说已导入或 hash 为已消费字节。事后重读/前后 stat 不能提供 exact bytes 保证。须由 root 裁决受控字节流/不可变 staging 及依赖闭包方案；若 staging 改写引用须分别记录原输入与实际解析快照，不能把两者混同。未解决前明确 provenance incomplete，不得宣称完整 2C 此路径闭合。保持既有 GDML 支持，不擅自拒绝公开能力。 |
| 偏置 | BiasingManager.cc:463 LoadFromConfig 消费主 INI，543 AttachOperators，649 ConstructThreadOperators，690 BeginThreadRun，748 EndThreadRun。 | 配置 provenance 复用公共 IniReader 声明历史；显式 process/legacy→展开规则的派生链均保留。Master计划、worker真实TLS绑定/wrapped匹配/完成收据分开，不拿 proposal/applied 当物理无偏性。 |

## 稳定对象与真实投影

- 材料使用类型+原配置名称，区分 isotope/element/material 命名空间；别名映射到同一 G4 对象时记录关系，不能用指针作 ID。保留当前大小写不敏感查找行为，身份原始名与归一查找键分离。导出 NIST请求、自定义密度/auto依赖、组分模式/顺序/归一前后、同位素丰度与实际单位；不导出未消费温压为已支持参数。
- INI 几何按稳定配置对象名，模板隐式对象按模板约定名称或确定配置序号并说明；布尔工具/操作、placement副本规则、STL、vis、region 分字段，JSON Pointer 转义 / 和 ~。不为每个 parameterised copy 假造配置对象；副本 material/transform 是运行观测，scope另列。
- GDML 不用 GetLogicalVolumeStore 全局序号或指针标身份。沿导入 root 的稳定普通 touchable 路径标 placement，LV采用文件内定义身份/共享关系；同名多LV须有确定拓扑映射，不得任意 GetVolume(name) 选择。Q1明确拒绝的路径碰撞和bias大小写碰撞仍拒绝。导入后推断不到原始XML字段请求时标 requested unknown，并注明 imported observation，不伪造输入字段来源。
- 偏置规则身份不能仅取可重复 display name；以实际规则配置身份（显式section，legacy展开的particle/process派生关系）为根，保留大小写区分的 process，目标LV用几何稳定ID引用。enabled/factor/primary/secondaries/minWeight/maxInteractions/volumes 均来自实际规则。规则不存在/禁用时不留下陈旧活动字段。

## 应用证据可观察层

材料 LoadMaterials 当前在 Configure 内即 BuildAll，可在成功 BuildIsotope/Element/Material 后读取真实 G4对象的 Z/N/A、密度、组分并给 KernelConstructed；不等于材料已被某LV使用，不伪造 ThreadApplied。自动/NIST GetMaterial 会懒构造，导出不能调用它。

几何 configure 只证明 VolumeNode/模板已接受；BuildWorld 成功后读取实际 root 下 solid种类/可读尺寸、LV material、placement、region 关系，按可观察字段标 KernelConstructed，未有通用solid反射的字段保持 ManagerAccepted 并给原因。world共享构造不等于各worker SD/field已安装；后两者由 root/field 的真实回调独立记录。region physics为几何与PhysicsManager联合应用，几何报告实际挂接/根体及cut对象，物理参数来源由root对应消费者提供。

偏置 AttachOperators成功只证明 master几何计划；ConstructThreadOperators证明该worker对象创建，BeginThreadRun tlsVerified+wrapped检查才可 ThreadApplied；EndThreadRun收据保留run/thread scope。现有 WorkerEvidence 是聚合每worker而非每规则，若要逐规则标applied必须补每规则/目标真实绑定收据，不能将总matchedRules复制到所有字段。配置字段factor成功传入operation可记录构造值，不提升为物理效果验证。

## 预定独占文件与专项

include/src Materials、Geometry、Biasing 目录内相关 Manager/reader/Messenger/factory/registry/builder/GdmlIO/StlReader；新增消费者专项拟 `scripts/test_effective_geometry_materials.py`（G4USIM_EXE），不改已有测试。新增adapter头可选 `include/Config/EffectiveConfigConsumer.hh` 必须由root统一拥有，子代理不自行创建重复公共类型。src/Templates及include/Templates接入需要root明确授权；公共 IniReader/InputProvenance 归 q1_field，不改其文件。

验收至少：同一字节快照值/历史链/哈希一致，重复和别名顺序，中文路径与改内容哈希变化，导出无副作用，/和~身份，模板/定义替换删除，合法和失败材料macro来源，真实材料构造值，GDML/STL/辅助输入闭包，configure无几何应用伪证据，构造后真实LV关系，1/2worker两run bias逐规则收据，失败保留旧revision/来源与部分失败边界，mode缺失兼容及冲突。正式建构由root统一，完成后由不同审查者交叉复核；专项通过不等于全部2C完成。

下一步：root确认 Field/EvidenceRecord、replace/remove/generation、成功macro回调及 InputSnapshot API，授权Templates并裁决GDML exact-read，再按上述真实消费者入口实施。

## 新执行者接续实现（q1_field，2026-10-29）

root重新授予Materials/Geometry/Templates独占（GdmlIO与Detector留root）；这不是重发前执行者任务。已完整读取本设计与1959信、Q1历史。现源码冻结供root增量构建，尚未跑新后端。

公开API：MaterialManager/GeometryManager均ExportEffectiveConfigFields() const -> vector<Field>、ExportEffectiveConfigEvidence() const -> Value(Array)、ConfirmEffectiveConfigMutation(command,Origin)。GeometryManager新增AcceptEffectiveConfig(const IniReader&)：主INI Configure成功后供root调用，保存template/config/check_overlaps/default_world_material及别名完整声明链；canonical-first按真实非空兼容规则选择。LoadGeometryConfig已有真实BuildNodesFromFile与typed rootNode，Configure时发布全部对象，不需要等BuildWorld或另行构造。成功Load/clear/Confirm均经ConsumerState Accept/Confirm stamp generation，移除对象不残留字段；失败load不发布成功字段。

输入链：MaterialIniReader和GeometryConfig用ReadFile bytes，候选LoadBytes原子发布；GetInputReader返回完整重复声明与同字节hash。GeometryConfig诊断两次strict/version扫描改用同一bytes，不重开。Templates基类用root提供的ConfigManager::LoadMainConfigBytes(filename,bytes)，Validate/Build/诊断共享；hierarchical复用GeometryConfig同bytes。参数化copies_file同bytes解析、返回顺序path/hash。STL返回实际解析的path/hash/format/lengthUnit，VolumeBuilder成功封闭solid后保存输入观察；不在configure伪称已读取尚未构造的STL。

材料投影：isotope/element/material命名空间稳定ID；Z/N/A与g/mole、同位素丰度、NIST/alias、density g/cm3/auto、state、组件模式/顺序/amount及输入清单。实际reader的case-preserving section map按字典序处理，provenance保留这一旧规则，不擅改为case-fold后的文本最后值获胜。重复键链保留；缺归属直接定义标runtime_unattributed，同值成功命令按精确对象前缀附来源，addNist alias单独保留。不导出未使用温压。BuildAll部分失败只记录失败/可能部分构造，不发布该次成功来源；既有Geant4缓存对象与新definition不同的观察标unknown。实际密度、Z/N/A、symbol/isotope丰度与flattened元素质量分数均从已存在对象读取，导出不调用懒构造getter。

几何投影：所有真实VolumeNode（含world、模板派生名字、用户对象）输出parent/shape/material、适用size/parameters、position/rotation、sensitive/bias/region/cuts、normal copyNo、replica/parameterised表、vis及boolean有序工具/transform。shape-specific混合参数明确标Geant4_internal_shape_specific，不假作全mm；独立长度/角度shape property转mm/deg。数组/layer/shield模板组合输入以derived来源保留完整声明上下文。unknown用户property不假称被消费。GDML placeholder仅import_descriptor，不导出虚假Box/AIR/size。

构造收据：GeometryManager BuildWorld成功且ApplyRegionPhysics后记录真实LV material、solid类型、Box尺寸、normal placement位置/copyNo、实际region与已请求cuts；不把master几何当worker SD/field。缺通用solid反射的细项不假applied。GdmlIO新ImportResult acceptedInputs/pathsha与untrackedInputs已消费，重复同路径/不同hash原序保留；imported placement用稳定普通路径+copyNo记录observed（请求未知），不构造假INI字段。STL/native输入额外观察不会增配置revision。root Recorder只在observed类型/值与配置一致且generation/hash符合时升级应用，其余保留observations。

独立验证：全部Templates与七个Materials/Geometry修改实现单元完成C++17 -fsyntax-only，exit0，无链接/Geant4构建，日志out/verification/2c-foundation/geometry-materials-syntax.log。新test_effective_geometry_materials.py默认实际独立编译MaterialIniReader/MaterialCommandParser/StlReader及公共输入工具，验证重复CRLF/hash/失败保留/真实封闭tetra STL，exit0；日志geometry-materials-input.log。--backend分支读取G4USIM_EXE，验证真实Configure导出density重复来源、特殊名字geometry typed节点、copies同字节hash、无几何伪applied和无运行目录，待root新构建执行。未修改主线runner/schema/ConfigSupport/Source/Physics/Field/Scoring/Action/CMake/GdmlIO；git diff --check通过。
