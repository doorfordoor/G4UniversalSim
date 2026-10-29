# E6 field/biasing schema 独立审查

结论：审查五类descriptor、生成器、ConfigManager和FieldConfig替换，未发现相对2C的新增消费/默认/休眠/大小写语义漂移。生成器未修改；`test_field_biasing_schema.py --component`（包含生成产物`--check`）在本审查回合通过。

- `src/Config/ConfigManager.cc:94-99`动态键表改用生成表，`field.<name>`及`biasing.xs.<particle>.<process>`字段与替换前清单一致；静态表替代原field/biasing手表，不引入全字段强制解析。
- `src/Field/FieldConfig.cc:250-273`仅把允许键集合来源替换为schema；原local非空无点后缀、global volumes专用拒绝继续保留。`295-314`保持局部volume和精度长度校验；`include/Field/FieldConfig.hh:45-48`与schema的0.01/0.25/0.01/0.001 mm默认一致。
- `src/Biasing/BiasingManager.cc:480-492`原休眠短路未改，schema规则明确不能提前解析休眠规则；`499-525`保持originalSection的hIoni、显式覆盖告警及apply_to_secondaries优先；`535-564`保持legacy列表/显式auto-on完整性要求。schema没有改变enabled=false规则仍会先读数值的历史事实。
- schema字段为external_only；structured不作scalar放行，地图路径仍由专用后端解析和哈希。过程匹配、worker TLS和模块三态实际策略未被schema代替。

新增正式探针`scripts/test_field_biasing_schema_review.py`（请登记backend/exe）：三类四例，非原suite重复：①缺gate的畸形动态section+NaN仍休眠接受，auto使相同内容进入解析并拒绝；②总gate开启但单rule disabled仍先解析NaN并拒绝；③混合大小写section/key保留Coil/hIoni身份、布尔词YES/ON、.001 cm→.01 mm与未指定精度默认值，两个true仍归一only_primary=false。

保留2C后端已独立执行通过，完整日志与SHA在`out/verification/e6-independent-schema-baseline/`，旧后端SHA256=fbb7c56e820d3d36e5f87a3ef2995d55c554d4c5cb38dbaa75191422d4bc37f0。候选build02仍在主负责人构建队列，新增脚本支持`--executable ... --baseline ... --evidence ...`做相同输入的完整field/biasing快照差分。Configure级证据不外推transport或物理验证。

候选独立实测补记：build02可执行文件SHA256=dcd96ad49c1c3756a4be4175c7182681de93979c7c5cbc354b1941d4eee2c785，四例对两后端均通过；接受/拒绝一致，两个接受病例的全部field/biasing快照字段（含来源及精度默认值）完全一致。日志与结构化记录位于`out/verification/e6-independent-schema-candidate/`。该轮没有修改C++/schema；新增正式探针请主负责人纳入runner后在最终冻结源码上复验。
