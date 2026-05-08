# G4UniversalSim Module API Index

本文档记录已经完成模块中可被后续模块调用的主要类、结构体、函数、文件位置与基本作用。后续每完成一个模块，应追加更新本文件，作为跨模块开发时的接口索引。

约定：

- 路径均相对于项目根目录 `G4UniversalSim/`。
- 本索引只记录稳定的对外接口，不记录内部 helper 函数。
- 若接口行为存在重要约定，例如大小写、默认值、异常行为，应在“说明”中写明。
- 全局命令前缀统一为 `/AIHL/`。
- 除非特殊说明：
    - Manager 持有业务状态；
    - Messenger 只解析 UI 命令并转发给 Manager；
    - DetectorConstruction 不保存材料、几何模板、biasing、scoring 业务状态；
    - GeometryRegistry 是 geometry 与 SD / Biasing / Scoring 之间的唯一 volume 查询桥梁；
    - OutputManager 不保证线程安全，多线程下应每个 worker 独立输出；
    - 所有涉及 biasing 的 scoring 必须同时保留 raw value 和 weighted value；
    - 所有模块不得直接 std::exit，错误应通过 exception 或 G4Exception 上抛。
------

## Utils 模块

模块职责：提供字符串处理、文件路径与文本读写、Geant4 单位解析、Geant4 名称生成等基础工具。

依赖约束：

- `StringUtils` 不依赖 Geant4。
- `FileUtils` 不依赖 Geant4。
- `UnitParser` 依赖 `G4SystemOfUnits.hh` 与 `G4UnitsTable.hh`。
- `G4NameUtils` 不依赖项目内其他模块。

### StringUtils

位置：

- 头文件：`include/Utils/StringUtils.hh`
- 源文件：`src/Utils/StringUtils.cc`

命名空间：`StringUtils`

| 接口 | 基本作用 |
|---|---|
| `std::string Trim(const std::string& s)` | 去除字符串首尾空白。 |
| `std::string LTrim(const std::string& s)` | 去除字符串左侧空白。 |
| `std::string RTrim(const std::string& s)` | 去除字符串右侧空白。 |
| `std::vector<std::string> Split(const std::string& s, char delimiter, bool skipEmpty = true)` | 按字符分隔字符串；默认跳过空元素。 |
| `std::vector<std::string> SplitWhitespace(const std::string& s)` | 按任意空白字符拆分。 |
| `std::string ToLower(const std::string& s)` | 转小写。 |
| `std::string ToUpper(const std::string& s)` | 转大写。 |
| `bool StartsWith(const std::string& s, const std::string& prefix)` | 判断前缀。 |
| `bool EndsWith(const std::string& s, const std::string& suffix)` | 判断后缀。 |
| `bool Contains(const std::string& s, const std::string& token)` | 判断是否包含子串。 |
| `std::string RemoveComment(const std::string& s, const std::vector<char>& commentChars = {'#', ';'})` | 删除行内注释，默认识别 `#` 和 `;`。 |
| `bool ToBool(const std::string& s)` | 解析布尔值，支持 `true/false`、`yes/no`、`on/off`、`1/0`，大小写不敏感。 |
| `std::string Join(const std::vector<std::string>& items, const std::string& delimiter)` | 用分隔符拼接字符串数组。 |

说明：

- `ToBool()` 解析失败会抛出 `std::runtime_error`，错误信息包含原始输入。
- `Split()` 默认不自动 `Trim` 每一项，调用方如需去空白应显式调用 `Trim()`。

### FileUtils

位置：

- 头文件：`include/Utils/FileUtils.hh`
- 源文件：`src/Utils/FileUtils.cc`

命名空间：`FileUtils`

| 接口 | 基本作用 |
|---|---|
| `bool Exists(const std::string& path)` | 判断路径是否存在。 |
| `bool IsFile(const std::string& path)` | 判断路径是否为普通文件。 |
| `bool IsDirectory(const std::string& path)` | 判断路径是否为目录。 |
| `void CreateDirectories(const std::string& path)` | 递归创建目录。 |
| `std::string CanonicalPath(const std::string& path)` | 返回弱规范化路径。 |
| `std::string AbsolutePath(const std::string& path)` | 返回绝对路径。 |
| `std::string JoinPath(const std::string& a, const std::string& b)` | 拼接两个路径片段。 |
| `std::string ParentPath(const std::string& path)` | 获取父路径。 |
| `std::string Filename(const std::string& path)` | 获取文件名。 |
| `std::string Extension(const std::string& path)` | 获取扩展名。 |
| `std::string ReadTextFile(const std::string& path)` | 读取整个文本文件。 |
| `void WriteTextFile(const std::string& path, const std::string& content)` | 写入文本文件，必要时创建父目录。 |

说明：

- 使用 C++17 `std::filesystem`，兼容 Windows/Linux。
- `CreateDirectories()`、`CanonicalPath()`、`AbsolutePath()`、`ReadTextFile()`、`WriteTextFile()` 失败时抛出 `std::runtime_error`，错误信息包含路径。

### UnitParser

位置：

- 头文件：`include/Utils/UnitParser.hh`
- 源文件：`src/Utils/UnitParser.cc`

命名空间：`UnitParser`

| 接口 | 基本作用 |
|---|---|
| `double ParseDouble(const std::string& text)` | 解析无单位 double。 |
| `double ParseDoubleWithUnit(const std::string& text)` | 解析数字或数字加任意 Geant4 已注册单位。 |
| `double ParseLength(const std::string& text)` | 解析长度，支持 `nm`、`um`、`mm`、`cm`、`m`。 |
| `double ParseEnergy(const std::string& text)` | 解析能量，支持 `eV`、`keV`、`MeV`、`GeV`。 |
| `double ParseTime(const std::string& text)` | 解析时间，支持 `ns`、`us`、`ms`、`s`。 |
| `double ParseAngle(const std::string& text)` | 解析角度，支持 `deg`、`rad`。 |
| `std::vector<double> ParseVectorDouble(const std::string& text, char delimiter = ',')` | 解析无单位 double 数组。 |
| `std::vector<double> ParseVectorWithUnit(const std::string& text, char delimiter = ',')` | 解析带单位或无单位 double 数组。 |

说明：

- 返回值为 Geant4 内部单位体系下的 `double`。
- `ParseLength()`、`ParseEnergy()`、`ParseTime()`、`ParseAngle()` 会检查单位类型；不支持的单位会抛出 `std::runtime_error`。
- 无单位输入按纯数值返回，例如 `"10.5"` 返回 `10.5`。
- 解析失败时抛出 `std::runtime_error`，错误信息包含原始输入。

### G4NameUtils

位置：

- 头文件：`include/Utils/G4NameUtils.hh`
- 源文件：`src/Utils/G4NameUtils.cc`

命名空间：`G4NameUtils`

| 接口 | 基本作用 |
|---|---|
| `std::string SanitizeName(const std::string& raw)` | 将非法字符替换为 `_`；空名称返回 `unnamed`。 |
| `std::string MakeUniqueName(const std::string& base, int index)` | 生成 `base_index` 形式的唯一名称。 |
| `std::string LogicalName(const std::string& base)` | 生成 logical volume 名称：`base_LV`。 |
| `std::string PhysicalName(const std::string& base)` | 生成 physical volume 名称：`base_PV`。 |
| `std::string SolidName(const std::string& base)` | 生成 solid 名称：`base_Solid`。 |
| `std::string RegionName(const std::string& base)` | 生成 region 名称：`base_Region`。 |

说明：

- 允许字符为字母、数字、下划线；其他字符替换为 `_`。
- `base` 会先经过 `SanitizeName()`。

------

## Config 模块

模块职责：读取 ini 文件，管理 `section/key/value` 结构，提供主配置与具名配置文件访问接口。

依赖约束：

- 不依赖 Geant4。
- 可依赖 `Utils/StringUtils.hh` 与 `Utils/FileUtils.hh`。
- 不依赖 Materials、Geometry、Detector、Physics、Actions、Hits、Scoring、Biasing、Output。

重要约定：

- `section` 与 `key` 均大小写不敏感，内部统一 `Trim + ToLower`。
- 默认 section 名称为 `global`。
- 同一 `section/key` 重复出现时，后者覆盖前者。
- ini 注释支持 `#` 和 `;`，包括行尾注释。
- `ConfigValue` 的 vector 解析会 `Trim` 每一项，并跳过空元素。

### IniReader

位置：

- 头文件：`include/Config/IniReader.hh`
- 源文件：`src/Config/IniReader.cc`

类：`IniReader`

| 接口 | 基本作用 |
|---|---|
| `void Load(const std::string& filename)` | 加载 ini 文件并解析。 |
| `bool HasSection(const std::string& section) const` | 判断 section 是否存在。 |
| `bool HasKey(const std::string& section, const std::string& key) const` | 判断 key 是否存在。 |
| `std::string GetString(const std::string& section, const std::string& key) const` | 获取字符串值；不存在则抛异常。 |
| `std::string GetString(const std::string& section, const std::string& key, const std::string& defaultValue) const` | 获取字符串值；不存在则返回默认值。 |
| `std::vector<std::string> GetSections() const` | 获取已解析 section 名称列表。 |
| `std::vector<std::string> GetKeys(const std::string& section) const` | 获取指定 section 下的 key 列表。 |
| `const std::string& GetFilename() const` | 获取当前加载文件路径。 |
| `void Clear()` | 清空已加载配置。 |

说明：

- 文件不存在、文件无法打开、读取失败会抛出 `std::runtime_error`。
- ini 行格式错误会抛出 `std::runtime_error`，错误信息包含文件名和行号。
- `GetString(section, key)` 在 section/key 不存在时抛出 `std::runtime_error`，错误信息包含 section/key。

### ConfigValue

位置：

- 头文件：`include/Config/ConfigValue.hh`
- 源文件：`src/Config/ConfigValue.cc`

类：`ConfigValue`

| 接口 | 基本作用 |
|---|---|
| `ConfigValue()` | 默认构造空值。 |
| `explicit ConfigValue(const std::string& value)` | 从字符串构造配置值。 |
| `const std::string& AsString() const` | 返回原始字符串。 |
| `int AsInt() const` | 转为 int。 |
| `double AsDouble() const` | 转为 double。 |
| `bool AsBool() const` | 转为 bool。 |
| `std::vector<std::string> AsStringVector(char delimiter = ',') const` | 转为字符串数组。 |
| `std::vector<int> AsIntVector(char delimiter = ',') const` | 转为 int 数组。 |
| `std::vector<double> AsDoubleVector(char delimiter = ',') const` | 转为 double 数组。 |
| `bool Empty() const` | 判断原始字符串是否为空。 |

说明：

- `AsBool()` 支持 `true/false`、`yes/no`、`on/off`、`1/0`，大小写不敏感。
- 数值或布尔解析失败会抛出 `std::runtime_error`。
- 不解析 Geant4 单位；如需单位解析，后续模块应使用 `UnitParser`。

### ConfigManager

位置：

- 头文件：`include/Config/ConfigManager.hh`
- 源文件：`src/Config/ConfigManager.cc`

类：`ConfigManager`

| 接口 | 基本作用 |
|---|---|
| `void LoadMainConfig(const std::string& filename)` | 加载主配置文件。 |
| `void LoadConfigFile(const std::string& name, const std::string& filename)` | 加载具名配置文件。 |
| `bool HasConfigFile(const std::string& name) const` | 判断具名配置是否已加载。 |
| `bool HasSection(const std::string& section) const` | 在主配置中判断 section 是否存在。 |
| `bool HasKey(const std::string& section, const std::string& key) const` | 在主配置中判断 key 是否存在。 |
| `std::string GetString(const std::string& section, const std::string& key) const` | 从主配置读取 string；不存在则抛异常。 |
| `std::string GetString(const std::string& section, const std::string& key, const std::string& defaultValue) const` | 从主配置读取 string；不存在则返回默认值。 |
| `int GetInt(const std::string& section, const std::string& key) const` | 从主配置读取 int；不存在则抛异常。 |
| `int GetInt(const std::string& section, const std::string& key, int defaultValue) const` | 从主配置读取 int；不存在则返回默认值。 |
| `double GetDouble(const std::string& section, const std::string& key) const` | 从主配置读取 double；不存在则抛异常。 |
| `double GetDouble(const std::string& section, const std::string& key, double defaultValue) const` | 从主配置读取 double；不存在则返回默认值。 |
| `bool GetBool(const std::string& section, const std::string& key) const` | 从主配置读取 bool；不存在则抛异常。 |
| `bool GetBool(const std::string& section, const std::string& key, bool defaultValue) const` | 从主配置读取 bool；不存在则返回默认值。 |
| `std::vector<std::string> GetVector(const std::string& section, const std::string& key, char delimiter = ',') const` | 从主配置读取字符串数组；不存在则抛异常。 |
| `std::vector<std::string> GetVector(const std::string& section, const std::string& key, const std::vector<std::string>& defaultValue, char delimiter = ',') const` | 从主配置读取字符串数组；不存在则返回默认值。 |
| `ConfigValue GetValue(const std::string& section, const std::string& key) const` | 从主配置读取轻量值包装器；不存在则抛异常。 |
| `ConfigValue GetValue(const std::string& section, const std::string& key, const std::string& defaultValue) const` | 从主配置读取轻量值包装器；不存在则返回默认值包装器。 |
| `std::string GetStringFrom(const std::string& configName, const std::string& section, const std::string& key, const std::string& defaultValue = "") const` | 从具名配置读取 string；不存在则返回默认值。 |
| `ConfigValue GetValueFrom(const std::string& configName, const std::string& section, const std::string& key) const` | 从具名配置读取轻量值包装器；不存在则抛异常。 |
| `std::vector<std::string> GetSections() const` | 获取主配置 section 列表。 |
| `std::vector<std::string> GetKeys(const std::string& section) const` | 获取主配置中指定 section 的 key 列表。 |
| `std::string GetMainConfigPath() const` | 获取主配置路径。 |
| `void Clear()` | 清空主配置和具名配置。 |

说明：

- 主配置未加载时调用读取接口会抛出 `std::runtime_error`。
- 缺失 section/key 且调用无默认值接口时会抛出 `std::runtime_error`，错误信息包含 section/key。
- 具名配置名称大小写不敏感，内部统一 `Trim + ToLower`。

------

## Output 模块

模块职责：统一管理输出目录、CSV 写入、1D/2D 直方图、run summary，并为后续 `RunAction`、`EventAction`、`ScoringManager`、`SensitiveDetector` 提供统一输出入口。

依赖约束：

- 不依赖 Geant4。
- 可依赖 `Utils/FileUtils.hh` 与 `Utils/StringUtils.hh`。
- 不依赖 Materials、Geometry、Detector、Physics、Actions、Hits、Scoring、Biasing。
- `OutputManager` 不直接认识 `ParticleHit`、`ScorerBase`、`RunAction`、`EventAction`，只接收轻量 record。

重要约定：

- 默认输出目录为 `output`。
- 默认 thread id 为 `0`。
- 默认启用线程后缀，格式为 `_t0`、`_t1`。
- `Histogram1D::GetEntries()` 和 `Histogram2D::GetEntries()` 记录 `Fill()` 调用次数；bin content、underflow、overflow 存储权重和。
- `CsvWriter::WriteHeader()` 只允许写一次；写入 row 时如果 header 已存在会检查列数。

### OutputRecord

位置：

- 头文件：`include/Output/OutputRecord.hh`

结构体：`HitRecord`

| 字段 | 基本作用 |
|---|---|
| `int eventID` | event 编号。 |
| `int trackID` | track 编号。 |
| `int parentID` | parent track 编号。 |
| `std::string particleName` | 粒子名称。 |
| `double edep` | 能量沉积。 |
| `double ndep` | 非电离能量沉积预留字段。 |
| `double stepLength` | step 长度。 |
| `double x0, y0, z0` | step 起点位置。 |
| `double x1, y1, z1` | step 终点位置。 |
| `double px, py, pz` | 动量方向或动量分量预留字段。 |
| `double kineticEnergy` | 动能。 |
| `std::string processName` | 过程名称。 |
| `std::string volumeName` | volume 名称。 |
| `double weight` | track weight，用于未来 biasing 加权统计。 |
| `double LETcalc` | LET 预留字段。 |
| `double LETstep` | LET step 预留字段。 |

结构体：`EventEdepRecord`

| 字段 | 基本作用 |
|---|---|
| `int eventID` | event 编号。 |
| `double rawEdep` | 未加权 event edep。 |
| `double weightedEdep` | 加权 event edep，通常为 `edep * weight` 累加。 |

### CsvWriter

位置：

- 头文件：`include/Output/CsvWriter.hh`
- 源文件：`src/Output/CsvWriter.cc`

类：`CsvWriter`

| 接口 | 基本作用 |
|---|---|
| `CsvWriter()` | 默认构造。 |
| `explicit CsvWriter(const std::string& filename)` | 构造并打开 CSV 文件。 |
| `void Open(const std::string& filename)` | 打开 CSV 文件，自动创建父目录。 |
| `bool IsOpen() const` | 判断文件是否打开。 |
| `void WriteHeader(const std::vector<std::string>& columns)` | 写 CSV header；只能写一次。 |
| `void WriteRow(const std::vector<std::string>& values)` | 写字符串行，执行 CSV 转义。 |
| `void WriteRow(std::initializer_list<std::string> values)` | 便利 overload，支持 `WriteRow({"a", "b"})`。 |
| `void WriteRow(const std::vector<double>& values)` | 写 double 行。 |
| `void WriteRow(const std::vector<int>& values)` | 写 int 行。 |
| `void Flush()` | flush 文件。 |
| `void Close()` | 关闭文件。 |
| `void SetPrecision(int precision)` | 设置 double 输出精度。 |
| `int GetPrecision() const` | 获取 double 输出精度。 |
| `const std::string& GetFilename() const` | 获取当前文件名。 |

说明：

- 字符串字段包含逗号、双引号、换行时会用双引号包裹，内部双引号写成两个双引号。
- 文件打开、写入、flush 失败时抛出 `std::runtime_error`，错误信息包含文件名。

### Histogram1D

位置：

- 头文件：`include/Output/Histogram1D.hh`
- 源文件：`src/Output/Histogram1D.cc`

类：`Histogram1D`

| 接口 | 基本作用 |
|---|---|
| `Histogram1D()` | 默认构造未配置直方图。 |
| `Histogram1D(const std::string& name, int bins, double min, double max)` | 构造并配置 1D 直方图。 |
| `void Configure(const std::string& name, int bins, double min, double max)` | 配置直方图。 |
| `void Fill(double value, double weight = 1.0)` | 填充直方图。 |
| `void Merge(const Histogram1D& other)` | 合并兼容直方图。 |
| `void Reset()` | 清空 bin、underflow、overflow、entries、sumWeight。 |
| `void WriteCSV(const std::string& filename) const` | 写出 CSV。 |
| `const std::string& GetName() const` | 获取名称。 |
| `int GetBins() const` | 获取 bin 数。 |
| `double GetMin() const` | 获取下界。 |
| `double GetMax() const` | 获取上界。 |
| `double GetBinContent(int bin) const` | 获取指定 bin 权重和。 |
| `double GetUnderflow() const` | 获取 underflow 权重和。 |
| `double GetOverflow() const` | 获取 overflow 权重和。 |
| `double GetEntries() const` | 获取 Fill 调用次数。 |
| `double GetSumWeight() const` | 获取总权重和。 |

说明：

- `value < min` 进入 underflow；`value >= max` 进入 overflow。
- CSV 列为 `bin, low_edge, high_edge, center, count`。
- `Merge()` 要求 name、bins、min、max 完全一致，否则抛出 `std::runtime_error`。

### Histogram2D

位置：

- 头文件：`include/Output/Histogram2D.hh`
- 源文件：`src/Output/Histogram2D.cc`

类：`Histogram2D`

| 接口 | 基本作用 |
|---|---|
| `Histogram2D()` | 默认构造未配置直方图。 |
| `Histogram2D(const std::string& name, int xBins, double xMin, double xMax, int yBins, double yMin, double yMax)` | 构造并配置 2D 直方图。 |
| `void Configure(const std::string& name, int xBins, double xMin, double xMax, int yBins, double yMin, double yMax)` | 配置 2D 直方图。 |
| `void Fill(double x, double y, double weight = 1.0)` | 填充 2D 直方图。 |
| `void Merge(const Histogram2D& other)` | 合并兼容 2D 直方图。 |
| `void Reset()` | 清空 bin、underflow、overflow、entries。 |
| `void WriteCSV(const std::string& filename) const` | 写出 CSV。 |
| `const std::string& GetName() const` | 获取名称。 |
| `double GetUnderflow() const` | 获取 underflow 权重和。 |
| `double GetOverflow() const` | 获取 overflow 权重和。 |
| `double GetEntries() const` | 获取 Fill 调用次数。 |

说明：

- 任一轴低于下界计入总 underflow；任一轴高于或等于上界计入总 overflow。
- CSV 列为 `x_bin, y_bin, x_low, x_high, y_low, y_high, count`。

### RunSummary

位置：

- 头文件：`include/Output/RunSummary.hh`
- 源文件：`src/Output/RunSummary.cc`

类：`RunSummary`

| 接口 | 基本作用 |
|---|---|
| `void Set(const std::string& key, const std::string& value)` | 设置字符串 key-value。 |
| `void Set(const std::string& key, int value)` | 设置 int key-value。 |
| `void Set(const std::string& key, double value)` | 设置 double key-value。 |
| `void SetBool(const std::string& key, bool value)` | 设置 bool key-value。 |
| `bool Has(const std::string& key) const` | 判断 key 是否存在。 |
| `std::string Get(const std::string& key, const std::string& defaultValue = "") const` | 获取 value；不存在返回默认值。 |
| `void AddMessage(const std::string& message)` | 添加普通消息。 |
| `void AddWarning(const std::string& warning)` | 添加 warning。 |
| `void WriteText(const std::string& filename) const` | 写人类可读 summary。 |
| `void WriteCSV(const std::string& filename) const` | 写机器可读 summary。 |
| `void Clear()` | 清空 summary。 |

### OutputManager

位置：

- 头文件：`include/Output/OutputManager.hh`
- 源文件：`src/Output/OutputManager.cc`

类：`OutputManager`

| 接口 | 基本作用 |
|---|---|
| `void SetOutputDir(const std::string& outputDir)` | 设置输出目录，空字符串会回退到 `output`。 |
| `const std::string& GetOutputDir() const` | 获取输出目录。 |
| `void SetThreadId(int threadId)` | 设置 thread id。 |
| `int GetThreadId() const` | 获取 thread id。 |
| `void EnableThreadSuffix(bool enable)` | 开关线程后缀。 |
| `bool IsThreadSuffixEnabled() const` | 查询线程后缀开关。 |
| `std::string MakeOutputPath(const std::string& filename) const` | 拼接输出目录与文件名。 |
| `std::string MakeThreadFilename(const std::string& baseName) const` | 为文件名添加 `_tN` 后缀。 |
| `void Initialize()` | 创建输出目录。 |
| `void OpenHitFile()` | 打开 `hits_tN.csv` 或 `hits.csv` 并写 header。 |
| `void OpenEventEdepFile()` | 打开 `event_edep_tN.csv` 或 `event_edep.csv` 并写 header。 |
| `void WriteHit(const HitRecord& record)` | 写 hit record；首次调用自动打开文件。 |
| `void WriteEventEdep(const EventEdepRecord& record)` | 写 event edep record；首次调用自动打开文件。 |
| `void WriteHitRow(const std::vector<std::string>& values)` | 写 hit 原始 CSV 行。 |
| `void WriteEventEdepRow(const std::vector<std::string>& values)` | 写 event edep 原始 CSV 行。 |
| `void AddHistogram1D(const Histogram1D& hist)` | 注册 1D 直方图。 |
| `Histogram1D& GetHistogram1D(const std::string& name)` | 获取可修改 1D 直方图。 |
| `const Histogram1D& GetHistogram1D(const std::string& name) const` | 获取只读 1D 直方图。 |
| `bool HasHistogram1D(const std::string& name) const` | 判断 1D 直方图是否存在。 |
| `void WriteHistogram1D(const std::string& name)` | 写出指定 1D 直方图，文件名为 `hist_[name]_tN.csv`。 |
| `void WriteAllHistograms()` | 写出所有 1D 直方图。 |
| `RunSummary& GetRunSummary()` | 获取 summary。 |
| `const RunSummary& GetRunSummary() const` | 获取只读 summary。 |
| `void WriteRunSummary()` | 写出 `run_summary.txt`。 |
| `void Flush()` | flush 已打开 CSV。 |
| `void Close()` | 关闭已打开 CSV。 |

说明：

- Hit CSV header 包含 `eventID, trackID, parentID, particle, edep, ndep, stepLength, x0, y0, z0, x1, y1, z1, px, py, pz, kineticEnergy, process, volume, weight, LETcalc, LETstep`。
- Event edep CSV header 包含 `eventID, raw_edep, weighted_edep`。
- 获取不存在的 histogram 会抛出 `std::runtime_error`。

------

## Core 模块

模块职责：保存全局仿真上下文，协调配置加载、输出初始化和后续 Manager 生命周期，为 `main.cc` 提供简洁入口。

依赖约束：

- `SimulationContext` 不依赖 Geant4。
- `SimulationManager` 依赖各业务 Manager 的 public 接口，负责创建、持有并连接 Config / Output / Materials / Geometry / Physics / Source / Biasing / Scoring 等 manager。
- `AppMessenger` 依赖 Geant4 UI command，但只修改 `SimulationManager` / `SimulationContext`，不直接操作 Detector、Physics、Scoring、Biasing 或 run。

重要约定：

- `SimulationContext` 默认 `outputDir = "output"`、`numThreads = 1`、`interactive = false`、`checkOverlaps = true`、`dryRun = false`。
- seed 为可选状态；调用 `GetSeed()` 前可用 `HasSeed()` 判断。
- `SimulationManager::Initialize()` 执行 `BuildManagers()`、`LoadConfig()`、`Configure()`、初始化 `OutputManager`、写基础 `RunSummary`。
- `MaterialManager`、`GeometryManager`、`PhysicsManager`、`SourceManager`、`BiasingManager`、`ScoringManager` 由 `SimulationManager::BuildManagers()` 幂等创建。
- `DetectorConstruction`、`PhysicsList`、`PrimaryGeneratorAction`、`ActionInitialization` 通过工厂函数创建并交给 Geant4 RunManager 生命周期管理，`SimulationManager` 不长期 owning 它们。

### SimulationContext

位置：

- 头文件：`include/Core/SimulationContext.hh`
- 源文件：`src/Core/SimulationContext.cc`

类：`SimulationContext`

| 接口 | 基本作用 |
|---|---|
| `SimulationContext()` | 构造并设置默认状态。 |
| `void SetMainConfig(const std::string& path)` | 设置主配置文件路径。 |
| `const std::string& GetMainConfig() const` | 获取主配置文件路径。 |
| `void SetOutputDir(const std::string& dir)` | 设置输出目录；空字符串回退到 `output`。 |
| `const std::string& GetOutputDir() const` | 获取输出目录。 |
| `void SetSeed(unsigned long seed)` | 设置随机种子状态。 |
| `unsigned long GetSeed() const` | 获取随机种子；未设置则抛异常。 |
| `bool HasSeed() const` | 判断 seed 是否已设置。 |
| `void SetNumThreads(int n)` | 设置线程数；`n <= 0` 抛异常。 |
| `int GetNumThreads() const` | 获取线程数。 |
| `void SetInteractive(bool interactive)` | 设置交互模式。 |
| `bool IsInteractive() const` | 判断是否交互模式。 |
| `void SetMacroFile(const std::string& path)` | 设置 macro 文件路径。 |
| `const std::string& GetMacroFile() const` | 获取 macro 文件路径。 |
| `bool HasMacroFile() const` | 判断 macro 文件是否已设置。 |
| `void SetVerboseLevel(int level)` | 设置 verbose level。 |
| `int GetVerboseLevel() const` | 获取 verbose level。 |
| `void SetCheckOverlaps(bool enable)` | 设置几何 overlap 检查开关。 |
| `bool GetCheckOverlaps() const` | 获取 overlap 检查开关。 |
| `void SetDryRun(bool enable)` | 设置 dry-run 开关。 |
| `bool IsDryRun() const` | 获取 dry-run 开关。 |
| `void SetRunName(const std::string& name)` | 设置 run name。 |
| `const std::string& GetRunName() const` | 获取 run name。 |
| `void Clear()` | 重置为默认状态。 |

### SimulationManager

位置：

- 头文件：`include/Core/SimulationManager.hh`
- 源文件：`src/Core/SimulationManager.cc`

类：`SimulationManager`

| 接口 | 基本作用 |
|---|---|
| `SimulationManager()` | 构造并创建 ConfigManager / OutputManager。 |
| `SimulationContext& GetContext()` | 获取可修改上下文。 |
| `const SimulationContext& GetContext() const` | 获取只读上下文。 |
| `void SetMainConfig(const std::string& filename)` | 设置主配置路径，并清除 loaded/configured/initialized 状态。 |
| `void SetOutputDir(const std::string& outputDir)` | 设置输出目录，并同步已存在的 OutputManager。 |
| `void SetNumThreads(int n)` | 设置线程数。 |
| `void SetSeed(unsigned long seed)` | 设置 seed。 |
| `void SetMacroFile(const std::string& filename)` | 设置 macro 文件。 |
| `void SetInteractive(bool interactive)` | 设置交互模式。 |
| `void SetVerboseLevel(int level)` | 设置 verbose level。 |
| `void SetCheckOverlaps(bool enable)` | 设置 overlap 检查开关。 |
| `void LoadConfig()` | 加载 `context.mainConfig` 到 ConfigManager。 |
| `void Initialize()` | 执行核心初始化顺序并写出基础 run summary。 |
| `void Configure()` | 从主配置读取 `[run]`、`[output]`、`[materials]`、`[geometry]`、`[physics]`、`[source]`、`[biasing]`、`[scoring]` 等配置并转发给对应 manager。 |
| `void BuildManagers()` | 幂等创建并连接 ConfigManager / OutputManager / MaterialManager / GeometryManager / PhysicsManager / SourceManager / BiasingManager / ScoringManager 及已实现 messenger。 |
| `void PrintSummary() const` | 向 `std::cout` 打印当前上下文和状态。 |
| `bool IsConfigured() const` | 查询是否已配置。 |
| `bool IsInitialized() const` | 查询是否已初始化。 |
| `ConfigManager* GetConfigManager()` | 获取 ConfigManager。 |
| `OutputManager* GetOutputManager()` | 获取 OutputManager。 |
| `MaterialManager* GetMaterialManager()` | 获取 MaterialManager；`BuildManagers()` 后非空。 |
| `GeometryManager* GetGeometryManager()` | 获取 GeometryManager；`BuildManagers()` 后非空。 |
| `PhysicsManager* GetPhysicsManager()` | 获取 PhysicsManager；`BuildManagers()` 后非空。 |
| `SourceManager* GetSourceManager()` | 获取 SourceManager；`BuildManagers()` 后非空。 |
| `BiasingManager* GetBiasingManager()` | 获取 BiasingManager；`BuildManagers()` 后非空。 |
| `ScoringManager* GetScoringManager()` | 获取 ScoringManager；`BuildManagers()` 后非空。 |
| `std::unique_ptr<DetectorConstruction> CreateDetectorConstruction() const` | 创建使用当前 `GeometryManager*` 的 DetectorConstruction，调用方交给 RunManager。 |
| `std::unique_ptr<G4VModularPhysicsList> CreatePhysicsList() const` | 按 PhysicsManager 当前模式创建 reference 或 manual physics list，调用方交给 RunManager。 |
| `std::unique_ptr<PrimaryGeneratorAction> CreatePrimaryGeneratorAction() const` | 创建使用当前 `SourceManager*` 的 primary generator action。 |
| `std::unique_ptr<ActionInitialization> CreateActionInitialization() const` | 创建连接 Source / Scoring / Output 的 ActionInitialization，调用方交给 RunManager。 |
| `std::function<G4VSensitiveDetector*()> CreateSensitiveDetectorFactory() const` | 创建使用当前 `ScoringManager*` 的 SensitiveDetector factory，供 DetectorConstruction 绑定 SD。 |
| `std::function<void(const GeometryRegistry&)> CreateGeometryPostBuildCallback() const` | 创建几何构建后回调，当前用于 biasing operator attach。 |

说明：

- `Configure()` 读取 `[run] threads`、`seed`、`interactive`、`macro`、`verbose`、`check_overlaps`、`run_name`、`[output] dir`，并按已实现模块读取 materials / geometry / physics / source / biasing / scoring 配置；缺失时使用默认值或保持 manager 默认状态。
- `Initialize()` 会创建输出目录并写出 `run_summary.txt`。
- 当前不创建 `G4RunManager`，不直接调用 `SetUserInitialization()` / `SetUserAction()`；只提供安全创建入口。

### AppMessenger

位置：

- 头文件：`include/Core/AppMessenger.hh`
- 源文件：`src/Core/AppMessenger.cc`

类：`AppMessenger : public G4UImessenger`

| UI 命令 | 基本作用 |
|---|---|
| `/sim/app/setMainConfig` | 调用 `SimulationManager::SetMainConfig()`。 |
| `/sim/app/setOutputDir` | 调用 `SimulationManager::SetOutputDir()`。 |
| `/sim/app/setNumThreads` | 调用 `SimulationManager::SetNumThreads()`。 |
| `/sim/app/setSeed` | 调用 `SimulationManager::SetSeed()`。 |
| `/sim/app/setVerbose` | 调用 `SimulationManager::SetVerboseLevel()`。 |
| `/sim/app/setCheckOverlaps` | 调用 `SimulationManager::SetCheckOverlaps()`。 |
| `/sim/app/printSummary` | 调用 `SimulationManager::PrintSummary()`。 |

说明：

- `AppMessenger` 不启动 run，不构建几何，不修改 Detector/Physics/Scoring/Biasing。

------

## Materials 模块

模块职责：统一管理 Geant4 同位素、元素、材料定义与对象缓存；支持 NIST 材料、自定义同位素元素、自定义复合材料，以及 `/AIHL/material/...` UI/macro 命令。

依赖约束：

- 可依赖 `Utils/StringUtils.hh`、`Utils/FileUtils.hh`。
- 可依赖 Geant4 material 与 UI command 相关头文件。
- 不依赖 Geometry、Templates、Detector、Physics、Source、Actions、Hits、Scoring、Biasing。

重要约定：

- 名称查找大小写不敏感，内部 map key 使用 `Trim + ToLower`；Geant4 对象名保留定义中的原始名称。
- isotope abundance 内部使用 `0~1`，支持 `90%` 输入；总和必须接近 `1.0`，不自动归一化。
- mass fraction 总和必须接近 `1.0`，不自动归一化。
- `Clear()` 只清理 manager 内部定义和缓存，不 delete Geant4 已注册对象。
- `SetLocked(true)` 后新增定义会抛出 `std::runtime_error`。
- Materials UI 命令统一使用 `/AIHL/material/...`，应尽量在 `/run/initialize` 前调用。

### MaterialDefinition

位置：

- 头文件：`include/Materials/MaterialDefinition.hh`

主要类型：

| 类型 | 基本作用 |
|---|---|
| `enum class MaterialComponentMode` | 组件模式：`ByMassFraction`、`ByAtomCount`、`ByVolumeFraction`。 |
| `enum class MaterialSourceType` | 材料来源：`Nist`、`Custom`。 |
| `struct IsotopeDefinition` | 保存同位素定义数据，不创建 `G4Isotope`。 |
| `struct IsotopeComponent` | 保存同位素组成与丰度。 |
| `struct ElementDefinition` | 保存普通元素或同位素组成元素定义，不创建 `G4Element`。 |
| `struct MaterialComponent` | 保存材料组件名称、质量分数或原子数。 |
| `struct MaterialDefinition` | 保存材料定义，不创建 `G4Material`。 |

### MaterialCommandParser

位置：

- 头文件：`include/Materials/MaterialCommandParser.hh`
- 源文件：`src/Materials/MaterialCommandParser.cc`

类：`MaterialCommandParser`

| 接口 | 基本作用 |
|---|---|
| `ParseKeyValueLine(const std::string& line)` | 解析 `key=value` 命令行，支持双引号 value。 |
| `Require(...)` | 从解析结果中读取必需 key，缺失则抛异常。 |
| `ParseDensity(const std::string& text)` | 解析 `g/cm3`、`g/cm^3`、`kg/m3`、`kg/m^3`、`mg/cm3`、`mg/cm^3`。 |
| `ParseMolarMass(const std::string& text)` | 解析 `g/mole`、`g/mol`、`kg/mole`、`kg/mol`。 |
| `ParseFraction(const std::string& text)` | 解析 `0~1` 或百分比，如 `90%`。 |
| `ParseMode(const std::string& text)` | 解析 `atom`、`atom_count`、`mass`、`mass_fraction`、`volume_fraction`。 |
| `ParseMaterialComponents(...)` | 解析 `A:1,B:2` 或 `A:0.7,B:0.3`。 |
| `ParseIsotopeComponents(...)` | 解析 `B10:0.90,B11:0.10`。 |

### MaterialIniReader

位置：

- 头文件：`include/Materials/MaterialIniReader.hh`
- 源文件：`src/Materials/MaterialIniReader.cc`

类：`MaterialIniReader`

| 接口 | 基本作用 |
|---|---|
| `void Load(const std::string& filename)` | 解析 material.ini。 |
| `bool HasIsotope/HasElement/HasMaterial(...) const` | 判断定义是否存在。 |
| `GetIsotopeDefinition/GetElementDefinition/GetMaterialDefinition(...) const` | 获取定义；不存在则抛异常。 |
| `GetIsotopeNames/GetElementNames/GetMaterialNames() const` | 获取定义名称列表。 |
| `std::vector<std::string> GetNistMaterialNames() const` | 获取 `[NIST] materials` 列表。 |
| `void Clear()` | 清空已解析定义。 |

说明：

- 支持 `[NIST]`、`[isotope.NAME]`、`[element.NAME]`、`[material.NAME]`。
- 兼容旧式简化段落 `[Alias] material = G4_AIR`，会注册为 alias 指向 NIST 材料。

### MaterialFactory

位置：

- 头文件：`include/Materials/MaterialFactory.hh`
- 源文件：`src/Materials/MaterialFactory.cc`

类：`MaterialFactory`

| 接口 | 基本作用 |
|---|---|
| `G4Isotope* BuildIsotope(const IsotopeDefinition& def)` | 创建 `G4Isotope`。 |
| `G4Element* BuildElement(...)` | 根据定义创建普通或同位素元素。 |
| `G4Element* BuildSimpleElement(...)` | 用 `z/a` 创建 `G4Element`。 |
| `G4Element* BuildIsotopicElement(...)` | 用 `AddIsotope` 创建同位素元素。 |
| `G4Material* BuildNistMaterial(const std::string& nistName)` | 从 `G4NistManager` 获取 NIST 材料。 |
| `G4Material* BuildCustomMaterial(...)` | 根据 density/components 创建自定义材料。 |
| `G4Material* BuildMaterial(...)` | 根据 source 类型分派构建。 |

### MaterialManager

位置：

- 头文件：`include/Materials/MaterialManager.hh`
- 源文件：`src/Materials/MaterialManager.cc`

类：`MaterialManager`

| 接口 | 基本作用 |
|---|---|
| `void LoadMaterials(const std::string& filename)` | 解析并构建 material.ini。 |
| `AddIsotopeDefinition/AddElementDefinition/AddMaterialDefinition(...)` | 添加定义。 |
| `BuildIsotope/BuildElement/BuildMaterial(const std::string& name)` | 构建指定对象。 |
| `void BuildAll()` | 构建所有 pending 定义，支持材料依赖多轮解析。 |
| `GetMaterial/GetElement/GetIsotope(...) const` | 获取对象；不存在则抛异常。 |
| `HasMaterial/HasElement/HasIsotope(...) const` | 判断对象或定义是否存在。 |
| `G4Material* BuildNistMaterial(const std::string& name)` | 构建并缓存 NIST 材料。 |
| `G4Material* BuildCustomMaterial(const MaterialDefinition& desc)` | 构建并缓存自定义材料。 |
| `RegisterMaterial/RegisterElement/RegisterIsotope(...)` | 手动注册 Geant4 对象指针。 |
| `GetMaterialNames/GetElementNames/GetIsotopeNames() const` | 获取当前缓存名称。 |
| `PrintMaterials/PrintElements/PrintIsotopes/PrintAll() const` | 打印缓存内容。 |
| `void Clear()` | 清理 manager 内部缓存和定义。 |
| `void SetLocked(bool locked)` | 锁定或解锁定义修改。 |
| `bool IsLocked() const` | 查询锁定状态。 |

### MaterialMessenger

位置：

- 头文件：`include/Materials/MaterialMessenger.hh`
- 源文件：`src/Materials/MaterialMessenger.cc`

类：`MaterialMessenger : public G4UImessenger`

| UI 命令 | 基本作用 |
|---|---|
| `/AIHL/material/load <filename>` | 调用 `MaterialManager::LoadMaterials()`。 |
| `/AIHL/material/print` | 调用 `PrintAll()`。 |
| `/AIHL/material/list` | 调用 `PrintAll()`。 |
| `/AIHL/material/addNist name=<alias> nist=<G4_NAME>` | 构建 NIST 材料并可按 alias 注册。 |
| `/AIHL/material/addIsotope ...` | 添加并构建同位素。 |
| `/AIHL/material/addElement ...` | 添加并构建普通元素。 |
| `/AIHL/material/addElementFromIsotopes ...` | 添加并构建同位素组成元素。 |
| `/AIHL/material/addMaterial ...` | 添加并构建材料。 |
| `/AIHL/material/buildAll` | 构建所有 pending 定义。 |
| `/AIHL/material/setLocked true/false` | 设置锁定状态。 |
| `/AIHL/material/clear` | 清空 manager 内部缓存和定义。 |

------

## Geometry 数据模块

模块职责：描述几何数据、解析几何 ini、验证 volume 关系，并提供 Geant4 volume 指针注册表。该模块只是数据层，不创建 `G4Box`、`G4Tubs`、`G4LogicalVolume`、`G4PVPlacement` 或 `G4Region`。

依赖约束：

- `VolumeNode` / `GeometryConfig` / `GeometryUtils` 不依赖 Materials、Templates、VolumeBuilder、Detector、Physics、Scoring、Biasing。
- `GeometryRegistry` 只前向引用并缓存 `G4LogicalVolume*`、`G4VPhysicalVolume*`，不拥有生命周期，不 delete Geant4 指针。
- 允许依赖 Utils 与 Config。

重要约定：

- `Vec3` 保存 Geant4 内部长度单位；`Rotation3` 保存 Geant4 内部角度单位。
- world volume 通过 `parentName.empty()` 判断。
- `GeometryConfig` 允许 `sensitive` 和 `bias` 同时为 true。
- `GeometryRegistry` 重复注册同名 logical/physical volume 时采用“后者覆盖前者”，便于 `/run/reinitializeGeometry` 后刷新 registry。

### GeometryTypes

位置：

- 头文件：`include/Geometry/GeometryTypes.hh`

主要类型：

| 类型 | 基本作用 |
|---|---|
| `enum class VolumeShape` | 几何形状枚举：`Box`、`Tubs`、`Sphere`、`Orb`、`Cone`、`Trapezoid`、`Unknown`。 |
| `enum class PlacementType` | placement 类型预留：`Normal`、`Replica`、`Parameterised`、`Assembly`。 |
| `struct Vec3` | 三维长度向量。 |
| `struct Rotation3` | 三维旋转角。 |
| `struct ProductionCut` | gamma/electron/positron/proton production cut；小于 0 表示未设置。 |
| `struct VisualAttributes` | 可视化属性预留，不创建 `G4VisAttributes`。 |

### VolumeNode

位置：

- 头文件：`include/Geometry/VolumeNode.hh`
- 源文件：`src/Geometry/VolumeNode.cc`

类：`VolumeNode`

| 接口/字段 | 基本作用 |
|---|---|
| `name`, `parentName` | volume 名称与父 volume 名称。 |
| `shape`, `shapeName` | 解析后的形状与原始形状字符串。 |
| `materialName` | 材料名称，后续由 `MaterialManager` 解析。 |
| `size`, `position`, `rotation` | 基础尺寸、相对父 volume 的位置和旋转。 |
| `parameters` | tubs/sphere/cone 等形状的额外参数。 |
| `sensitive`, `bias` | 后续 SD 与 biasing 标记。 |
| `regionName`, `productionCuts`, `hasProductionCuts` | region/cuts 数据预留。 |
| `visual` | 可视化数据预留。 |
| `children` | 树结构子节点。 |
| `userProperties` | 未识别或模板扩展属性。 |
| `IsWorld/HasParent/HasRegion/IsSensitive/IsBiasVolume()` | 状态查询。 |
| `AddChild/HasChildren/GetChildren/GetChildrenMutable()` | 子节点管理。 |
| `SetProperty/HasProperty/GetProperty()` | 扩展属性访问。 |
| `ShapeAsString()` | shape 转字符串。 |
| `ToString()` | 调试字符串。 |
| `ValidateBasic()` | 数据级检查，不访问材料、不创建几何、不检查 overlap。 |

### GeometryUtils

位置：

- 头文件：`include/Geometry/GeometryUtils.hh`
- 源文件：`src/Geometry/GeometryUtils.cc`

命名空间：`GeometryUtils`

| 接口 | 基本作用 |
|---|---|
| `ParseShape / ShapeToString` | 解析和输出形状名。 |
| `ParsePlacementType / PlacementTypeToString` | 解析和输出 placement 类型。 |
| `ParseVec3(text, parseAsLength)` | 解析三维向量，支持逗号或空白分隔。 |
| `ParseRotation3(text)` | 解析三维角度。 |
| `ParseParameterList(text, parseWithUnits)` | 解析参数列表，支持单位。 |
| `ParseProductionCuts(values)` | 解析 `cut.gamma`、`cut.e-`、`cut.e+`、`cut.proton`。 |
| `IsValidVolumeName / NormalizeVolumeName / ValidateVolumeName` | volume 名称处理。 |
| `ValidateBoxSize` | 检查 box x/y/z > 0。 |
| `ValidateTubsParameters` | 检查 tubs 参数合法性。 |
| `MakePath(parentPath, childName)` | 生成 `/world/child` 风格路径。 |

### GeometryConfig

位置：

- 头文件：`include/Geometry/GeometryConfig.hh`
- 源文件：`src/Geometry/GeometryConfig.cc`

类：`GeometryConfig`

| 接口 | 基本作用 |
|---|---|
| `void Load(const std::string& filename)` | 解析几何 ini 文件。 |
| `void LoadFromConfigManager(const ConfigManager& config)` | 从 `[geometry] config` 读取路径并加载。 |
| `void Clear()` | 清空 flat volume 和索引。 |
| `bool HasVolume(const std::string& name) const` | 判断 volume 是否存在。 |
| `GetVolume / GetVolumeMutable` | 获取 volume 数据。 |
| `GetVolumeNames()` | 获取 flat volume 名称。 |
| `GetSensitiveVolumeNames()` | 获取 sensitive volume 名称。 |
| `GetBiasVolumeNames()` | 获取 bias volume 名称。 |
| `GetRegionNames()` | 获取 region 名称集合。 |
| `const std::vector<VolumeNode>& GetFlatVolumes() const` | 获取 flat volume 列表。 |
| `VolumeNode BuildTree() const` | 将 flat list 转为 world 根节点树。 |
| `void AddVolume(const VolumeNode& node)` | 手动添加 volume。 |
| `void Validate() const` | 检查 world、parent、循环、shape、size、cuts 等。 |
| `const std::string& GetFilename() const` | 获取配置文件路径。 |

说明：

- 支持 `[world]` 与 `[volume.NAME]`。
- 未识别 key 会保存到 `VolumeNode::userProperties`。
- 不检查材料存在性，不检查 overlap。

### GeometryRegistry

位置：

- 头文件：`include/Geometry/GeometryRegistry.hh`
- 源文件：`src/Geometry/GeometryRegistry.cc`

类：`GeometryRegistry`

| 接口 | 基本作用 |
|---|---|
| `Clear()` | 清理 registry。 |
| `RegisterLogicalVolume / RegisterPhysicalVolume` | 注册 Geant4 volume 指针；空指针报错。 |
| `HasLogicalVolume / HasPhysicalVolume` | 查询是否注册。 |
| `GetLogicalVolume / GetPhysicalVolume` | 获取指针；不存在则抛异常。 |
| `MarkSensitiveVolume / MarkBiasVolume` | 标记 sensitive/bias volume，可先于注册调用。 |
| `IsSensitiveVolume / IsBiasVolume` | 查询标记。 |
| `GetLogicalVolumeNames / GetPhysicalVolumeNames` | 获取注册名称。 |
| `GetSensitiveVolumeNames / GetBiasVolumeNames` | 获取标记名称。 |
| `GetSensitiveLogicalVolumes / GetBiasLogicalVolumes` | 获取已注册且被标记的 logical volumes。 |
| `RegisterRegionName / HasRegionName / GetRegionName` | 记录 volume 到 regionName 的映射。 |
| `PrintSummary()` | 打印 registry 数量摘要。 |

------

## Templates 模块

模块职责：把模板配置转换为 `VolumeNode` 树，不创建任何 Geant4 solid、logical volume、physical volume 或 region。

依赖约束：
- 可依赖 `Utils`、`Config`、`Geometry` 数据模块。
- 不依赖 Materials、GeometryManager、VolumeBuilder、Detector、Physics、Source、Actions、Hits、Scoring、Biasing。
- 不直接 include `G4Box.hh`、`G4LogicalVolume.hh`、`G4PVPlacement.hh` 等几何构建头文件。

重要约定：
- 所有模板返回以 world 为根节点的 `VolumeNode` 树。
- 模板只保存 `materialName` 字符串，不检查材料是否存在。
- `sensitive`、`bias`、`regionName`、`productionCuts`、`visual` 会保留到 `VolumeNode`，供后续 SD、Biasing、Region/Cuts、Vis 模块使用。
- `ArrayTemplate` 第一版生成普通 `VolumeNode`，不使用 replica 或 parameterisation。
- `GDMLTemplate` 第一版只生成 placeholder 数据节点，不调用 `G4GDMLParser`。

### GeometryTemplate

位置：
- 头文件：`include/Templates/GeometryTemplate.hh`
- 源文件：`src/Templates/GeometryTemplate.cc`

类：`GeometryTemplate`

| 接口 | 基本作用 |
|---|---|
| `virtual std::string Name() const = 0` | 返回模板名称。 |
| `virtual VolumeNode BuildNodes(const ConfigManager& config) const = 0` | 从已加载配置构建 world 根节点。 |
| `virtual VolumeNode BuildNodesFromFile(const std::string& filename) const` | 从配置文件构建 world 根节点。 |
| `virtual VolumeNode BuildNodes(const GeometryConfig& geometryConfig) const` | 从几何数据配置构建 world 根节点，默认调用 `BuildTree()`。 |
| `virtual void ValidateConfig(const ConfigManager& config) const` | 模板级配置检查入口。 |

### SimpleBoxTemplate

位置：
- 头文件：`include/Templates/SimpleBoxTemplate.hh`
- 源文件：`src/Templates/SimpleBoxTemplate.cc`

类：`SimpleBoxTemplate : public GeometryTemplate`

基本作用：
- 从 `[world]` 和 `[target]` 构建 `world -> Target`。
- world 固定为 box；target 默认 box、默认 `sensitive=true`、默认 `bias=false`。
- 支持 `region`、`cut.gamma`、`cut.e-`、`cut.e+`、`cut.proton` 和 `[visual.target]`。

### LayeredDeviceTemplate

位置：
- 头文件：`include/Templates/LayeredDeviceTemplate.hh`
- 源文件：`src/Templates/LayeredDeviceTemplate.cc`

类：`LayeredDeviceTemplate : public GeometryTemplate`

基本作用：
- 从 `[layers]` 和 `[layer.NAME]` 构建多层器件结构。
- 每层为 box，`size = xy.x, xy.y, thickness`。
- 支持 `auto_stack=true` 沿 z 方向自动堆叠，默认整体居中；也支持 `z_start` 和 `gap`。
- 保存每层 `material`、`sensitive`、`bias`、`region`、production cuts 和 visual 属性。

### HierarchicalVolumeTemplate

位置：
- 头文件：`include/Templates/HierarchicalVolumeTemplate.hh`
- 源文件：`src/Templates/HierarchicalVolumeTemplate.cc`

类：`HierarchicalVolumeTemplate : public GeometryTemplate`

基本作用：
- 复用 `GeometryConfig` 解析 `[world]` 与 `[volume.NAME]`，返回通用 parent-child `VolumeNode` 树。
- 用于非固定模板、显式层级配置场景。

### ArrayTemplate

位置：
- 头文件：`include/Templates/ArrayTemplate.hh`
- 源文件：`src/Templates/ArrayTemplate.cc`

类：`ArrayTemplate : public GeometryTemplate`

基本作用：
- 从 `[array]` 构建规则阵列。
- 生成 `name_i_j_k` 命名的普通子 `VolumeNode`，直接挂到 world。
- 支持 `element_size`、`counts`、`pitch`、`center`、`sensitive`、`bias`、`region`。

### ShieldingTemplate

位置：
- 头文件：`include/Templates/ShieldingTemplate.hh`
- 源文件：`src/Templates/ShieldingTemplate.cc`

类：`ShieldingTemplate : public GeometryTemplate`

基本作用：
- 从 `[shielding]`、`[shield.NAME]` 和可选 `[detector]` 构建简单屏蔽层模型。
- 第一版支持 box 屏蔽层沿 z 方向堆叠。
- 保存 shield 的 `material`、`bias`、`region`，保存 detector 的 `sensitive` 和 `region`。

### GDMLTemplate

位置：
- 头文件：`include/Templates/GDMLTemplate.hh`
- 源文件：`src/Templates/GDMLTemplate.cc`

类：`GDMLTemplate : public GeometryTemplate`

基本作用：
- 从 `[gdml] file` 构建 placeholder world。
- 在 `userProperties` 保存 `gdml_file`、`gdml_world_name`、`sensitive_volumes`、`bias_volumes`。
- 不导入 GDML，不依赖 Xerces，不要求 Geant4 开启 GDML。

### TemplateFactory

位置：
- 头文件：`include/Templates/TemplateFactory.hh`
- 源文件：`src/Templates/TemplateFactory.cc`

类：`TemplateFactory`

| 接口 | 基本作用 |
|---|---|
| `static std::unique_ptr<GeometryTemplate> Create(const std::string& name)` | 按名称创建模板实例。 |
| `static std::vector<std::string> AvailableTemplates()` | 返回可用模板名称。 |

说明：
- 模板名大小写不敏感。
- 支持 `simple_box/simple`、`layered_device/layered`、`hierarchical`、`array`、`shielding`、`gdml`。
- 未知模板名会抛出 `std::runtime_error`。

------

## GeometryManager / VolumeBuilder / GeometryMessenger 模块

模块职责：完成 Geant4 几何闭环。`GeometryManager` 管几何状态与 dirty 标志，`VolumeBuilder` 把 `VolumeNode` 树转换成真实 Geant4 几何对象，`GeometryMessenger` 只负责 `/AIHL/geometry/...` 命令转发。

依赖约束：
- 可依赖 Utils、Config、Materials、Geometry 数据模块、Templates 模块和 Geant4 geometry/UI 基础类。
- 不依赖 Detector、Physics、Source、Actions、Hits、Scoring、Biasing。
- 不实现 DetectorConstruction，不绑定 SensitiveDetector，不 attach biasing operator，不启动 run。

重要约定：
- 推荐工作流：用 `/AIHL/geometry/...` 修改 `GeometryManager` 状态，再用 Geant4 原生命令 `/run/reinitializeGeometry` 触发重新构建。
- `GeometryManager::BuildWorld()` 应由后续 `DetectorConstruction::Construct()` 调用。
- `GeometryRegistry` 在每次 `BuildWorld()` 前清空，构建后反映最新 logical/physical/sensitive/bias/region 状态。
- `VolumeBuilder` 只通过 `MaterialManager::GetMaterial()` 取材料，不解析 material.ini。
- GDML 当前只保留 placeholder；`VolumeBuilder` 遇到 GDML placeholder 会明确报错，真正导入留到高级扩展。

### VolumeBuilder

位置：
- 头文件：`include/Geometry/VolumeBuilder.hh`
- 源文件：`src/Geometry/VolumeBuilder.cc`

类：`VolumeBuilder`

| 接口 | 基本作用 |
|---|---|
| `SetMaterialManager(MaterialManager*)` | 设置材料管理器；构建前必须非空。 |
| `SetRegistry(GeometryRegistry*)` | 设置几何注册表；构建前必须非空。 |
| `SetCheckOverlaps(bool)` / `GetCheckOverlaps()` | 控制传给 `G4PVPlacement` 的 overlap 检查开关。 |
| `SetDefaultWorldMaterial(...)` / `GetDefaultWorldMaterial()` | 设置 world material 缺省值，默认 `G4_AIR`。 |
| `Clear()` | 清理 builder 持有的 rotation/vis 辅助对象缓存。 |
| `BuildWorld(const VolumeNode& rootNode)` | 构建 world physical volume，并递归构建 children。 |
| `BuildLogicalVolume(const VolumeNode& node)` | 创建 solid、material、logical volume，并注册 logical volume。 |
| `BuildVolume(const VolumeNode& node, G4LogicalVolume* motherLogical)` | 构建并 placement 非 world volume。 |
| `CreateSolid(...)` | 根据 `VolumeShape` 分发到具体 solid 创建函数。 |
| `CreateBoxSolid/CreateTubsSolid/CreateSphereSolid/CreateOrbSolid/CreateConeSolid` | 创建对应 Geant4 solid。 |
| `CreateRotation(const VolumeNode& node)` | 按 X/Y/Z 顺序创建旋转；零旋转返回 `nullptr`。 |
| `CreateRegion(...)` | 创建/复用 `G4Region`，设置 production cuts，并向 registry 登记 region 名称。 |
| `ApplyVisualAttributes(...)` | 应用可视化属性，支持基础颜色、alpha、wireframe、visible。 |
| `GetRegistry()` | 返回当前 registry 指针。 |

说明：
- `Box` 的 `size.x/y/z` 按全长保存，创建 `G4Box` 时自动除以 2。
- `Tubs` 支持 5 参数 `rMin,rMax,halfZ,startPhi,deltaPhi`；若没有参数但有正 `size`，按 cylinder shorthand 处理。
- rotation 和 vis attributes 由 `VolumeBuilder` 持有，避免 logical/physical volume 引用悬空。

### GeometryManager

位置：
- 头文件：`include/Geometry/GeometryManager.hh`
- 源文件：`src/Geometry/GeometryManager.cc`

类：`GeometryManager`

| 接口 | 基本作用 |
|---|---|
| `SetMaterialManager(...)` / `GetMaterialManager()` | 设置并查询材料管理器，同时同步给 `VolumeBuilder`。 |
| `SetTemplate(...)` / `GetTemplateName()` | 设置模板名称，支持 `TemplateFactory` 中的模板别名，并标记 dirty。 |
| `LoadGeometryConfig(...)` / `GetGeometryConfigFile()` | 根据当前模板加载几何配置，保存 root node，并标记 dirty。 |
| `SetCheckOverlaps(...)` / `GetCheckOverlaps()` | 设置 overlap 检查，并同步给 builder。 |
| `SetDefaultWorldMaterial(...)` / `GetDefaultWorldMaterial()` | 设置 world 默认材料，并同步给 builder。 |
| `SetRootNode(...)` / `GetRootNode()` / `HasRootNode()` | 直接设置或访问当前 root `VolumeNode`。 |
| `MarkDirty()` / `ClearDirty()` / `IsDirty()` | 管理几何 dirty 状态。 |
| `BuildWorld()` | 清 registry，调用 `VolumeBuilder::BuildWorld()`，成功后清 dirty。 |
| `GetRegistry()` | 获取几何注册表。 |
| `GetVolumeBuilder()` | 获取底层 builder。 |
| `GetSensitiveVolumeNames()` / `GetBiasVolumeNames()` / `GetRegionNames()` | 获取当前几何标记信息。 |
| `PrintSummary()` / `PrintTree()` | 打印当前状态与 volume tree。 |
| `Clear()` | 清理当前 root/config/registry/builder 缓存，并标记 dirty。 |

### GeometryMessenger

位置：
- 头文件：`include/Geometry/GeometryMessenger.hh`
- 源文件：`src/Geometry/GeometryMessenger.cc`

类：`GeometryMessenger : public G4UImessenger`

| UI 命令 | 基本作用 |
|---|---|
| `/AIHL/geometry/setTemplate <templateName>` | 调用 `GeometryManager::SetTemplate()`。 |
| `/AIHL/geometry/loadConfig <filename>` | 调用 `GeometryManager::LoadGeometryConfig()`。 |
| `/AIHL/geometry/checkOverlaps <true|false>` | 调用 `GeometryManager::SetCheckOverlaps()`。 |
| `/AIHL/geometry/setDefaultWorldMaterial <materialName>` | 调用 `GeometryManager::SetDefaultWorldMaterial()`。 |
| `/AIHL/geometry/print` | 调用 `GeometryManager::PrintSummary()`。 |
| `/AIHL/geometry/printTree` | 调用 `GeometryManager::PrintTree()`。 |
| `/AIHL/geometry/clear` | 调用 `GeometryManager::Clear()`。 |
| `/AIHL/geometry/markModified` | 调用 `G4RunManager::GeometryHasBeenModified()`，不 rebuild、不 beamOn。 |

说明：
- Messenger 不保存几何业务状态，不直接创建任何 Geant4 几何对象。
- 改变几何状态的命令执行后会提示：如 run manager 已初始化，请在下一次 run 前使用 `/run/reinitializeGeometry`。

### Geometry Dynamic User Volumes 增量

位置：
- 头文件：`include/Geometry/GeometryManager.hh`
- 源文件：`src/Geometry/GeometryManager.cc`
- 命令头文件：`include/Geometry/GeometryMessenger.hh`
- 命令源文件：`src/Geometry/GeometryMessenger.cc`

新增职责：
- 支持通过 `/AIHL/geometry/...` 命令在当前 `VolumeNode` 树上追加用户体积。
- 用户体积只修改数据树，不直接创建 `G4Box`、`G4Tubs`、`G4LogicalVolume` 或 `G4PVPlacement`。
- 新增体积必须通过后续 `/run/reinitializeGeometry` 触发 `DetectorConstruction::Construct()`，再由 `GeometryManager::BuildWorld()` 真实构建。

新增 `GeometryManager` 接口：

| 接口 | 基本作用 |
|---|---|
| `AddVolume(const VolumeNode& node)` | 通用用户体积添加入口，验证后挂接到当前 root tree 并标记 dirty。 |
| `AddBoxVolume(...)` | 构造 box `VolumeNode` 并调用 `AddVolume()`。 |
| `AddTubsVolume(...)` | 构造 tubs `VolumeNode`，参数顺序为 `rMin,rMax,halfZ,startPhi,deltaPhi`。 |
| `RemoveUserVolume(const std::string& name)` | 只删除用户添加体积；第一版删除整个子树。 |
| `ClearUserAddedVolumes()` | 清空所有用户添加体积，并从当前树移除。 |
| `GetUserAddedVolumes()` | 返回用户添加体积副本。 |
| `GetUserAddedVolumeNames()` | 返回用户添加体积名称列表。 |
| `SetPreserveUserVolumesOnLoad(bool)` | 设置 `loadConfig` 后是否保留并重新挂接用户体积。 |
| `GetPreserveUserVolumesOnLoad()` | 查询保留策略。 |
| `ApplyUserAddedVolumes()` | 将 `userAddedVolumes_` 重新挂接到当前 root tree。 |
| `HasVolumeInCurrentTree(...)` | 查询当前最终树中是否存在 volume。 |
| `HasUserAddedVolume(...)` | 查询用户体积列表中是否存在 volume。 |
| `PrintUserAddedVolumes()` | 打印用户添加体积列表。 |

新增 `/AIHL/geometry/...` 命令：

| UI 命令 | 基本作用 |
|---|---|
| `/AIHL/geometry/addBox ...` | 解析 key=value，添加 box 用户体积。 |
| `/AIHL/geometry/addTubs ...` | 解析 key=value，添加 tubs/cylinder 用户体积。 |
| `/AIHL/geometry/addVolume ...` | 通用添加入口；第一版支持 `shape=box` 和 `shape=tubs`。 |
| `/AIHL/geometry/removeUserVolume <name>` | 删除用户添加体积。 |
| `/AIHL/geometry/clearUserVolumes` | 清空用户添加体积。 |
| `/AIHL/geometry/listUserVolumes` | 打印用户添加体积列表。 |
| `/AIHL/geometry/preserveUserVolumesOnLoad <true|false>` | 控制后续 `loadConfig` 是否保留用户添加体积。 |

说明：
- 命令参数 key 大小写不敏感，支持双引号 value，例如 `size="1 cm,1 cm,1 mm"`。
- `preserveUserVolumesOnLoad` 默认 `true`；设为 `false` 后，后续 `loadConfig` 会清空用户添加体积。
- 所有添加/删除命令成功后会标记 dirty，并提示使用 `/run/reinitializeGeometry`。

------

## Detector 模块

模块职责：作为 Geant4 几何入口。`DetectorConstruction` 只在 `Construct()` 中调用 `GeometryManager::BuildWorld()`，在 `ConstructSDandField()` 中根据 `GeometryRegistry` 绑定后续 Hits 模块提供的 `G4VSensitiveDetector`。

依赖约束：
- 可依赖 `GeometryManager` 和 `GeometryRegistry`。
- 可依赖 Geant4 detector construction、SD manager 和 UI command 基础类。
- 不依赖 Materials、Templates、VolumeBuilder、Physics、Source、Actions、Hits、Scoring、Biasing。

重要约定：
- Detector 不保存 templateName、geometry config filename 或 root `VolumeNode`。
- Detector 不解析 ini，不创建材料，不直接创建 `G4Box/G4Tubs/G4LogicalVolume/G4PVPlacement`。
- Detector 不 attach biasing operator，不实现 scoring，不启动 run。
- 几何命令仍归 `/AIHL/geometry/...`；DetectorMessenger 只管理 `/AIHL/detector/...`。

### DetectorConstruction

位置：
- 头文件：`include/Detector/DetectorConstruction.hh`
- 源文件：`src/Detector/DetectorConstruction.cc`

类：`DetectorConstruction : public G4VUserDetectorConstruction`

| 接口 | 基本作用 |
|---|---|
| `explicit DetectorConstruction(GeometryManager*)` | 绑定外部管理的 `GeometryManager`，不拥有其生命周期。 |
| `G4VPhysicalVolume* Construct() override` | 调用 `GeometryManager::BuildWorld()` 并缓存 world pointer。 |
| `void ConstructSDandField() override` | 根据 registry 中的 sensitive logical volumes 绑定 factory 创建的 SD。 |
| `SetGeometryManager(...)` / `GetGeometryManager()` | 设置或获取 geometry manager。 |
| `GetGeometryRegistry()` | 返回 `GeometryManager` 持有的 registry 指针。 |
| `GetWorldVolume()` | 返回最近一次 `Construct()` 的 world physical volume。 |
| `SetSensitiveDetectorEnabled(bool)` / `IsSensitiveDetectorEnabled()` | 控制是否执行 SD 绑定。 |
| `SetSensitiveDetectorName(...)` / `GetSensitiveDetectorName()` | 设置预留 SD 名称，默认 `AIHLParticleSD`。 |
| `SetVerboseLevel(int)` / `GetVerboseLevel()` | 设置 detector 输出详细程度。 |
| `PrintRegistrySummary()` | 打印 registry 摘要。 |
| `PrintSensitiveVolumes()` | 打印 sensitive volume 名称。 |
| `PrintBiasVolumes()` | 打印 bias volume 名称。 |
| `SetSensitiveDetectorFactory(std::function<G4VSensitiveDetector*()>)` | 后续 Hits 模块通过该 factory 接入真实 SD。 |
| `SetGeometryPostBuildCallback(std::function<void(const GeometryRegistry&)>)` | 设置几何构建后通用回调；DetectorConstruction 不保存 biasing 业务状态。 |

说明：
- factory 为空时，`ConstructSDandField()` 只输出 warning，不阻断几何构建。
- factory 返回空指针时抛出 `std::runtime_error`。
- 同名 sensitive detector 已存在时会复用已有 SD，避免 geometry reinitialize 时重复注册。
- sensitiveDetectorEnabled=false 时直接跳过 SD 绑定。
- `Construct()` 在 `GeometryManager::BuildWorld()` 成功后执行 post-build callback；当前用于 `BiasingManager::AttachOperators(registry)`。

### DetectorMessenger

位置：
- 头文件：`include/Detector/DetectorMessenger.hh`
- 源文件：`src/Detector/DetectorMessenger.cc`

类：`DetectorMessenger : public G4UImessenger`

| UI 命令 | 基本作用 |
|---|---|
| `/AIHL/detector/enableSD <true|false>` | 调用 `SetSensitiveDetectorEnabled()`。 |
| `/AIHL/detector/setSDName <name>` | 调用 `SetSensitiveDetectorName()`。 |
| `/AIHL/detector/printRegistry` | 调用 `PrintRegistrySummary()`。 |
| `/AIHL/detector/printSensitiveVolumes` | 调用 `PrintSensitiveVolumes()`。 |
| `/AIHL/detector/printBiasVolumes` | 调用 `PrintBiasVolumes()`。 |
| `/AIHL/detector/setVerbose <level>` | 调用 `SetVerboseLevel()`。 |
| `/AIHL/detector/printWorld` | 打印最近一次 world 是否已构建。 |

说明：
- DetectorMessenger 不管理 `/AIHL/geometry/...`、`/AIHL/material/...`、`/run/...` 命令。

### Core SimulationManager 集成更新

位置：
- 头文件：`include/Core/SimulationManager.hh`
- 源文件：`src/Core/SimulationManager.cc`
- App 命令源文件：`src/Core/AppMessenger.cc`

新增职责：
- `SimulationManager` 现在真正创建并持有 `MaterialManager`、`GeometryManager`。
- `SimulationManager` 创建 `MaterialMessenger` 和 `GeometryMessenger`，分别暴露 `/AIHL/material/...` 与 `/AIHL/geometry/...` 命令。
- `GeometryManager` 会通过 `SetMaterialManager(materialManager_.get())` 连接材料系统。
- `SimulationManager` 不长期拥有 `DetectorConstruction`；通过 `CreateDetectorConstruction()` 创建并让调用方转移给 `G4RunManager`。

新增/确认接口：

| 接口 | 基本作用 |
|---|---|
| `std::unique_ptr<DetectorConstruction> CreateDetectorConstruction() const` | 创建 `DetectorConstruction(geometryManager_.get())`，供 main.cc `release()` 给 `G4RunManager`。 |
| `MaterialManager* GetMaterialManager()` | 返回由 `SimulationManager` 持有的材料管理器。 |
| `GeometryManager* GetGeometryManager()` | 返回由 `SimulationManager` 持有的几何管理器。 |

配置读取：
- `[materials] file` 非空时调用 `MaterialManager::LoadMaterials(file)`。
- `[geometry] template` 非空时调用 `GeometryManager::SetTemplate(template)`。
- `[geometry] config` 非空时调用 `GeometryManager::LoadGeometryConfig(config)`。
- `[geometry] check_overlaps` 会同步到 `SimulationContext` 和 `GeometryManager`。
- `[geometry] default_world_material` 非空时调用 `GeometryManager::SetDefaultWorldMaterial(...)`。

初始化顺序：
1. `BuildManagers()`
2. 如设置 main config，则 `LoadConfig()`
3. `Configure()`
4. `OutputManager::Initialize()`
5. 写入基础 `RunSummary`

说明：
- 没有 main config 时不强制失败，保留默认 context。
- 没有 materials/geometry 配置时不强制失败，可后续通过 macro 命令加载。
- AppMessenger 命令前缀已从 `/sim/app/...` 统一为 `/AIHL/app/...`。

------

## Biasing 模块真实 XS 实现

模块职责：保存 biasing 配置，并实现 Geant4 cross-section biasing 的真实闭环。`BiasingMessenger` 只解析 `/AIHL/biasing/...` 命令并转发给 `BiasingManager`；`PhysicsList` / reference physics list 负责注册 `G4GenericBiasingPhysics` 并指定 biased particle/process；`BiasingManager::AttachOperators()` 在几何构建完成后通过 `GeometryRegistry` 把 `BiasingMultiParticleXS` attach 到目标 logical volume；实际截面变换由每个粒子的 `BiasingXS` 完成。

依赖约束：
- `BiasingConfig` 不依赖 Geant4 biasing classes。
- `BiasingManager` 可依赖 `ConfigManager`、`GeometryRegistry`、`Utils/StringUtils` 和 `BiasingMultiParticleXS`。
- `BiasingXS` / `BiasingMultiParticleXS` 可依赖 Geant4 biasing classes：`G4VBiasingOperator`、`G4BOptnChangeCrossSection`、`G4BiasingProcessInterface`。
- Biasing 模块不依赖 DetectorConstruction、ScoringManager、OutputManager；也不直接注册 physics constructor。

### BiasingConfig

位置：
- 头文件：`include/Biasing/BiasingConfig.hh`

主要类型：
| 类型 | 基本作用 |
|---|---|
| `enum class BiasingType` | 预留 biasing 类型：`None`、`CrossSection`、`Region`、`Importance`。 |
| `struct XSBiasRule` | 保存单个粒子的截面偏置规则。 |
| `struct BiasingConfig` | 保存 biasing enable 状态和 XS rule 列表。 |

`XSBiasRule` 关键字段：
- `particleName`
- `processNames`
- `factor`
- `onlyPrimary`
- `applyToSecondaries`
- `minWeight`
- `maxInteractions`
- `volumeNames`
- `enabled`

`XSBiasRule` 接口：
- `bool IsValid() const`
- `void Validate() const`
- `std::string ToString() const`

`BiasingConfig` 接口：
- `Clear()`
- `HasRules()`
- `GetEnabledXSRules()`
- `Validate()`

### BiasingManager

位置：
- 头文件：`include/Biasing/BiasingManager.hh`
- 源文件：`src/Biasing/BiasingManager.cc`

类：`BiasingManager`

| 接口 | 基本作用 |
|---|---|
| `Enable(bool)` / `IsEnabled()` | 设置或查询 biasing 总开关。 |
| `Clear()` | 清空配置和全局 bias volumes。 |
| `AddXSBiasRule(...)` | 添加或替换 XS rule。 |
| `CreateOrGetXSBiasRule(particleName)` | 按粒子名查找或创建 rule；查找大小写不敏感。 |
| `AddXSBiasParticle(...)` | 创建粒子 rule。 |
| `AddXSBiasProcess(particleName, processName)` | 给指定粒子 rule 添加 process。 |
| `AddXSBiasProcess(processName)` | 简化接口；仅当当前只有一个 rule 时允许。 |
| `SetXSBiasFactor(...)` | 设置截面偏置因子。 |
| `SetOnlyPrimary(...)` / `SetApplyToSecondaries(...)` | 设置 primary/secondary 作用策略，并自动避免语义冲突。 |
| `SetMinWeight(...)` | 设置最低权重限制。 |
| `SetMaxInteractions(...)` | 设置最大 bias 相互作用次数。 |
| `AddBiasVolume(...)` | 添加全局 bias volume。 |
| `AddBiasVolumeForParticle(...)` | 添加粒子 rule 专属 volume。 |
| `HasXSBiasRule(...)` / `GetXSBiasRule(...)` | 查询 rule。 |
| `GetXSBiasRules()` / `GetEnabledXSBiasRules()` | 获取规则列表。 |
| `GetBiasedParticles()` / `GetBiasedProcesses(...)` | 获取粒子和过程列表。 |
| `GetBiasVolumes()` | 返回全局 volume 与各 rule volume 的去重并集。 |
| `Validate()` | 校验所有 rule。 |
| `PrintSummary()` | 打印配置与 operator attach 摘要。 |
| `LoadFromConfig(const ConfigManager&)` | 从 `[biasing]` / `[biasing.xs]` 读取简化配置。 |
| `AttachOperators(const GeometryRegistry&)` | 根据规则和 `GeometryRegistry` 真实创建并 attach `BiasingMultiParticleXS`。 |
| `ClearOperators()` | 清空当前持有的 biasing operator；建议只在 geometry rebuild 前后使用。 |
| `AreOperatorsAttached()` | 查询当前是否已有 operator attach。 |
| `GetAttachedOperatorCount()` | 返回当前 manager 持有的 operator 数量。 |

### BiasingXS

位置：
- 头文件：`include/Biasing/BiasingXS.hh`
- 源文件：`src/Biasing/BiasingXS.cc`

类：`BiasingXS : public G4VBiasingOperator`

| 接口 | 基本作用 |
|---|---|
| `BiasingXS(const XSBiasRule&)` | 用单粒子 XS rule 创建 operator。 |
| `SetRule/GetRule` | 替换或查询规则。 |
| `SetXSBiasFactor/GetXSBiasFactor` | 设置或查询截面偏置因子。 |
| `SetProcessNames/GetProcessNames` | 设置或查询需要偏置的 process 名称；为空表示允许所有 wrapped process。 |
| `SetOnlyPrimary` / `SetApplyToSecondaries` | 控制 primary/secondary 作用策略。 |
| `SetMinWeight` / `SetMaxInteractions` | 控制最低权重和每 track 最大偏置相互作用次数。 |
| `StartRun()` | 校验粒子是否存在。 |
| `StartTracking(track)` | 重置当前 track 的偏置计数。 |
| `ProposeOccurenceBiasingOperation(...)` | 使用 wrapped process 的 current interaction length 计算 analog XS，并通过 `G4BOptnChangeCrossSection` 设置 biased XS。 |
| `OperationApplied(...)` | 标记 operation interaction occurred，并累加当前 track 的偏置次数。 |

说明：
- `BiasingXS` 不访问 `GeometryRegistry`、`ScoringManager`、`OutputManager`。
- 不手动修改 track weight；权重修正由 Geant4 biasing framework 和 `G4BOptnChangeCrossSection` 负责。

### BiasingMultiParticleXS

位置：
- 头文件：`include/Biasing/BiasingMultiParticleXS.hh`
- 源文件：`src/Biasing/BiasingMultiParticleXS.cc`

类：`BiasingMultiParticleXS : public G4VBiasingOperator`

| 接口 | 基本作用 |
|---|---|
| `AddParticle(const XSBiasRule&)` | 给当前 volume-level operator 添加一个粒子的 XS rule。 |
| `HasParticle(particleName)` | 大小写不敏感查询粒子 operator。 |
| `ClearParticles()` | 清空粒子 operator。 |
| `AttachToVolume(G4LogicalVolume*)` | 调用 Geant4 `AttachTo()` 绑定 logical volume。 |
| `StartRun()` | 转发到所有粒子 `BiasingXS`。 |
| `StartTracking(track)` | 根据 track particle 选择当前 `BiasingXS`。 |
| `ProposeOccurenceBiasingOperation(...)` / `OperationApplied(...)` | 转发到当前粒子的 `BiasingXS`。 |

说明：
- 一个 `BiasingMultiParticleXS` 对应一个 logical volume。
- `currentOperator_` 是实例成员，不使用全局状态。

### BiasingMessenger

位置：
- 头文件：`include/Biasing/BiasingMessenger.hh`
- 源文件：`src/Biasing/BiasingMessenger.cc`

命令前缀：`/AIHL/biasing/`

| 命令 | 转发到 |
|---|---|
| `/AIHL/biasing/enable <true|false>` | `BiasingManager::Enable` |
| `/AIHL/biasing/xs/addParticle <particle>` | `BiasingManager::AddXSBiasParticle` |
| `/AIHL/biasing/xs/addProcess <process>` | `BiasingManager::AddXSBiasProcess(process)` |
| `/AIHL/biasing/xs/addProcessForParticle <particle> <process>` | `BiasingManager::AddXSBiasProcess(particle, process)` |
| `/AIHL/biasing/xs/setFactor <particle> <factor>` | `BiasingManager::SetXSBiasFactor` |
| `/AIHL/biasing/xs/onlyPrimary <particle> <true|false>` | `BiasingManager::SetOnlyPrimary` |
| `/AIHL/biasing/xs/applyToSecondaries <particle> <true|false>` | `BiasingManager::SetApplyToSecondaries` |
| `/AIHL/biasing/xs/setMinWeight <particle> <value>` | `BiasingManager::SetMinWeight` |
| `/AIHL/biasing/xs/setMaxInteractions <particle> <n>` | `BiasingManager::SetMaxInteractions` |
| `/AIHL/biasing/xs/addVolume <volume>` | `BiasingManager::AddBiasVolume` |
| `/AIHL/biasing/xs/addVolumeForParticle <particle> <volume>` | `BiasingManager::AddBiasVolumeForParticle` |
| `/AIHL/biasing/validate` | `BiasingManager::Validate` |
| `/AIHL/biasing/print` | `BiasingManager::PrintSummary` |
| `/AIHL/biasing/clear` | `BiasingManager::Clear` |

说明：
- Messenger 不直接 new `BiasingXS`，不直接 attach logical volume，不操作 DetectorConstruction 或 PhysicsList。

SimulationManager 集成：
- `BuildManagers()` 会创建 `BiasingManager`。
- `BuildManagers()` 会创建 `BiasingMessenger`，暴露 `/AIHL/biasing/...`。
- `Configure()` 在 main config 已加载后调用 `biasingManager_->LoadFromConfig(*configManager_)`。
- 若 `BiasingManager` enabled，`Configure()` 会启用 PhysicsManager 的 generic biasing hook。
- `CreateDetectorConstruction()` 会设置 geometry post-build callback；几何构建完成后 callback 调用 `biasingManager_->AttachOperators(registry)`。
- `RunSummary` 写入 `biasing_enabled`、`biasing_xs_rule_count`、`biasing_operators_attached`、`biasing_attached_operator_count`。

与 Physics / Geometry / Scoring 的关系：
- Physics 模块注册 `G4GenericBiasingPhysics` 并为 enabled rule 调用 `PhysicsBias(particle, processNames)`。
- Geometry 构建完成后，`GeometryRegistry` 提供最新 logical volume 指针，BiasingManager 才能 attach operators。
- Scoring 通过 `HitRecord.weight = track->GetWeight()` 自动获得加权统计；Biasing 模块不直接写 scoring。

------

## Scoring 模块第一版

模块职责：提供 `ScorerBase` 抽象接口、`ScoringManager` 业务状态管理、`EdepScorer` 可用实现，以及 LET / Dose / Fluence 的轻量 stub。`SensitiveDetector` 将 `ParticleHit` 转为 `HitRecord` 后调用 `ScoringManager::ScoreHit()`；Scoring 只处理 `HitRecord`，不依赖 `ParticleHit` 或 `SensitiveDetector`。

依赖约束：
- 可依赖 `Output/OutputRecord.hh`、`Output/OutputManager.hh`、`Output/Histogram1D.hh`、`ConfigManager`、`Utils/StringUtils`、`Utils/UnitParser`。
- `ScoringMessenger` 可依赖 Geant4 UI command。
- 不依赖 DetectorConstruction、SensitiveDetector、ParticleHit、BiasingManager、ROOT、G4AnalysisManager。

### ScorerBase

位置：
- 头文件：`include/Scoring/ScorerBase.hh`
- 源文件：`src/Scoring/ScorerBase.cc`

类：`ScorerBase`

| 接口 | 基本作用 |
|---|---|
| `explicit ScorerBase(std::string name)` | 创建具名 scorer，名称不能为空。 |
| `GetName()` | 返回 scorer 原始名称。 |
| `SetEnabled(bool)` / `IsEnabled()` | 控制 scorer 是否参与生命周期分发。 |
| `BeginRun/EndRun` | run 生命周期入口，默认 no-op。 |
| `BeginEvent/EndEvent` | event 生命周期入口，默认 no-op。 |
| `ScoreHit(const HitRecord&)` | hit scoring 入口，默认 no-op。 |
| `Write(OutputManager&)` | 输出入口，默认 no-op。 |
| `Reset()` | 清理 scorer 内部状态，默认 no-op。 |

说明：
- `ScorerBase` 不持有 `OutputManager` 指针，不访问 `GeometryRegistry`。

### EdepScorer

位置：
- 头文件：`include/Scoring/EdepScorer.hh`
- 源文件：`src/Scoring/EdepScorer.cc`

类：`EdepScorer : public ScorerBase`

| 接口 | 基本作用 |
|---|---|
| `EdepScorer("edep")` | 创建 event-level energy deposition scorer。 |
| `BeginRun/EndRun` | run 级统计生命周期。 |
| `BeginEvent/EndEvent` | event 级 raw / weighted edep 生命周期，并在 EndEvent 填 histogram。 |
| `ScoreHit(const HitRecord&)` | 累积 `hit.edep` 与 `hit.edep * hit.weight`，并按 volume / particle 分类统计。 |
| `Write(OutputManager&)` | 写 `hist_edep_raw_tN.csv`、`hist_edep_weighted_tN.csv`、`edep_volume_summary_tN.csv`、`edep_particle_summary_tN.csv`。 |
| `EnableRawHistogram/EnableWeightedHistogram` | 控制 raw / weighted histogram。 |
| `ConfigureRawHistogram/ConfigureWeightedHistogram` | 配置 histogram bins/min/max。 |
| `EnableVolumeSummary/EnableParticleSummary` | 控制 volume / particle summary CSV。 |
| `GetCurrentEventRawEdep/GetCurrentEventWeightedEdep` | 查询当前 event 统计。 |
| `GetRunRawEdep/GetRunWeightedEdep` | 查询当前 run 统计。 |

说明：
- histogram 统计的是 event-level edep，不是 step-level edep。
- `EdepScorer` 不写 hits CSV，也不写 event_edep CSV。
- event_edep CSV 由 `ScoringManager` 统一写，避免与 EdepScorer 重复输出。

### LET / Dose / Fluence Scorer

位置：
- `include/Scoring/LETScorer.hh` / `src/Scoring/LETScorer.cc`
- `include/Scoring/DoseScorer.hh` / `src/Scoring/DoseScorer.cc`
- `include/Scoring/FluenceScorer.hh` / `src/Scoring/FluenceScorer.cc`

说明：
- `LETScorer` 可读取 `HitRecord::LETcalc` 并在显式开启 histogram 时填充；第一版不自行计算 LET。
- `DoseScorer` 第一版 no-op；真实 dose 需要 volume mass 或 geometry/material 数据。
- `FluenceScorer` 第一版 no-op；真实 fluence 需要面积、面通量或 track-length 定义。
- 三者都可被 `ScoringManager::RegisterScorer()` 注册。

### ScoringManager

位置：
- 头文件：`include/Scoring/ScoringManager.hh`
- 源文件：`src/Scoring/ScoringManager.cc`

类：`ScoringManager`

| 接口 | 基本作用 |
|---|---|
| `SetOutputManager(OutputManager*)` | 设置外部拥有的 output manager；不拥有生命周期。 |
| `Enable(bool)` / `IsEnabled()` | scoring 总开关。 |
| `EnableHitOutput(bool)` / `IsHitOutputEnabled()` | 控制是否写 hit CSV。 |
| `EnableEventEdepOutput(bool)` / `IsEventEdepOutputEnabled()` | 控制是否写 event edep CSV。 |
| `EnableEdepScoring(bool)` / `IsEdepScoringEnabled()` | 控制默认 EdepScorer。 |
| `EnableLETScoring(bool)` / `IsLETScoringEnabled()` | 控制 LETScorer stub。 |
| `EnableDoseScoring(bool)` / `IsDoseScoringEnabled()` | 控制 DoseScorer stub。 |
| `EnableFluenceScoring(bool)` / `IsFluenceScoringEnabled()` | 控制 FluenceScorer stub。 |
| `SetAutoCreateDefaultScorers(bool)` / `IsAutoCreateDefaultScorersEnabled()` | 控制 BeginRun 时是否自动创建默认 scorer。 |
| `ConfigureEdepHistogram(...)` | 配置 raw event edep histogram。 |
| `ConfigureWeightedEdepHistogram(...)` | 配置 weighted event edep histogram。 |
| `SetVerboseLevel(int)` / `GetVerboseLevel()` | 设置 verbose level。 |
| `RegisterScorer(std::unique_ptr<ScorerBase>)` | 注册 scorer；名称大小写不敏感去重。 |
| `EnsureDefaultScorers()` | 根据 edep/let/dose/fluence 开关创建默认 scorer。 |
| `HasScorer/GetScorer/GetScorerNames` | 查询 scorer。 |
| `BeginRun/EndRun` | run 生命周期分发。 |
| `BeginEvent/EndEvent` | event 生命周期分发，并在 EndEvent 写 `EventEdepRecord`。 |
| `ScoreHit(const HitRecord&)` | 聚合 raw/weighted edep，写 hit，并分发给 scorer。 |
| `GetCurrentEventRawEdep()` | 当前 event 原始 edep。 |
| `GetCurrentEventWeightedEdep()` | 当前 event 加权 edep，即 `hit.edep * hit.weight` 累积。 |
| `WriteAll()` | 调用所有 enabled scorer 的 `Write()`。 |
| `LoadFromConfig(const ConfigManager&)` | 读取 `[scoring]` 与 `[scoring.edep]`。 |
| `PrintSummary()` | 打印当前 scoring 状态。 |

配置：
- `[scoring] enabled/hits/event_edep/edep/let/dose/fluence/auto_create_default_scorers/verbose`
- `[scoring.edep] raw_histogram/weighted_histogram/bins/min/max/volume_summary/particle_summary`

### ScoringMessenger

位置：
- 头文件：`include/Scoring/ScoringMessenger.hh`
- 源文件：`src/Scoring/ScoringMessenger.cc`

命令前缀：`/AIHL/scoring/`

| UI 命令 | 转发到 |
|---|---|
| `/AIHL/scoring/enable <true|false>` | `ScoringManager::Enable` |
| `/AIHL/scoring/hits <true|false>` | `ScoringManager::EnableHitOutput` |
| `/AIHL/scoring/eventEdep <true|false>` | `ScoringManager::EnableEventEdepOutput` |
| `/AIHL/scoring/edep <true|false>` | `ScoringManager::EnableEdepScoring` |
| `/AIHL/scoring/let <true|false>` | `ScoringManager::EnableLETScoring` |
| `/AIHL/scoring/dose <true|false>` | `ScoringManager::EnableDoseScoring` |
| `/AIHL/scoring/fluence <true|false>` | `ScoringManager::EnableFluenceScoring` |
| `/AIHL/scoring/autoCreateScorers <true|false>` | `ScoringManager::SetAutoCreateDefaultScorers` |
| `/AIHL/scoring/setEdepHistogram bins=200 min=0 eV max=10 MeV` | `ScoringManager::ConfigureEdepHistogram` |
| `/AIHL/scoring/setWeightedEdepHistogram bins=200 min=0 eV max=10 MeV` | `ScoringManager::ConfigureWeightedEdepHistogram` |
| `/AIHL/scoring/verbose <level>` | `ScoringManager::SetVerboseLevel` |
| `/AIHL/scoring/print` | `ScoringManager::PrintSummary` |

SimulationManager 集成：
- `BuildManagers()` 会创建 `ScoringManager`。
- `BuildManagers()` 会创建 `ScoringMessenger`，暴露 `/AIHL/scoring/...`。
- `ScoringManager` 会连接 `OutputManager`。
- `Configure()` 调用 `scoringManager_->LoadFromConfig(*configManager_)`。
- `RunSummary` 写入 `scoring_enabled`、`scoring_hits_enabled`、`scoring_event_edep_enabled`、`scoring_edep_enabled`、`scoring_let_enabled`、`scoring_dose_enabled`、`scoring_fluence_enabled`、`scoring_auto_create_default_scorers`、`scoring_scorer_count`。
------

## Source 模块

模块职责：封装 Geant4 `G4GeneralParticleSource`，为后续 `ActionInitialization` / run action 体系提供稳定的 primary generator 入口；保留原生 `/gps/...` 命令，同时提供轻量 `/AIHL/source/...` preset 与常用设置命令。

依赖约束：
- 依赖 Geant4 GPS / particle table / units。
- 可依赖 `ConfigManager`、`Utils/StringUtils`、`Utils/UnitParser`。
- 不依赖 DetectorConstruction、GeometryManager、PhysicsList、Actions、Hits、Scoring、Biasing。

### PrimaryGeneratorAction

位置：
- 头文件：`include/Source/PrimaryGeneratorAction.hh`
- 源文件：`src/Source/PrimaryGeneratorAction.cc`

类：`PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction`

| 接口 | 基本作用 |
|---|---|
| `PrimaryGeneratorAction(SourceManager*)` | 使用外部 `SourceManager`；若为空则使用内部 fallback GPS。 |
| `GeneratePrimaries(G4Event*)` | 获取 GPS 并调用 `GeneratePrimaryVertex(event)`。 |
| `SetSourceManager(SourceManager*)` | 切换外部 SourceManager；不拥有生命周期。 |
| `GetSourceManager()` | 返回当前 SourceManager。 |
| `GetGPS()` | 若 SourceManager 存在则返回其 GPS，否则返回 fallback GPS。 |

说明：
- 不解析 source.ini。
- 不直接依赖 Detector / Geometry / Physics / Scoring / Biasing。
- `PrimaryGeneratorAction` 不拥有 `SourceManager`。

### SourceManager

位置：
- 头文件：`include/Source/SourceManager.hh`
- 源文件：`src/Source/SourceManager.cc`

类：`SourceManager`

| 接口 | 基本作用 |
|---|---|
| `GetGPS()` | 返回内部 `G4GeneralParticleSource`。 |
| `ResetGPS()` | 重建 GPS，并清空内部轻量状态。 |
| `LoadFromConfig(const ConfigManager&)` | 从 `[source]` section 读取 preset / particle / energy / position / direction。 |
| `ApplyPreset(name)` | 应用常用 preset。 |
| `SetParticle(name)` | 通过 `G4ParticleTable` 查找并设置粒子。 |
| `SetMonoEnergy(energy)` | 设置 mono 能量分布。 |
| `SetPointPosition(x,y,z)` | 设置点源位置。 |
| `SetDirection(x,y,z)` | 设置定向束流方向。 |
| `SetIsotropic()` | 设置各向同性角分布。 |
| `SetPlaneBeam(radius,z,direction)` | 设置平面圆形束斑。 |
| `SetVerboseLevel/GetVerboseLevel` | 管理 SourceManager verbose。 |
| `PrintSummary()` | 打印当前 source 轻量状态，并提示 `/gps/...` 仍可用。 |
| `IsConfigured()` | 返回是否经由 manager/preset/config 配置过。 |
| `GetParticleName()` / `GetMonoEnergy()` / `GetPresetName()` | 供 Core run summary 和状态输出使用。 |

支持 preset：
- `mono_proton`
- `proton_beam`
- `neutron_beam`
- `gamma_beam`
- `isotropic_neutron`
- `plane_proton_beam`

### SourceMessenger

位置：
- 头文件：`include/Source/SourceMessenger.hh`
- 源文件：`src/Source/SourceMessenger.cc`

类：`SourceMessenger : public G4UImessenger`

命令前缀：`/AIHL/source/`

| 命令 | 转发到 |
|---|---|
| `/AIHL/source/preset <name>` | `SourceManager::ApplyPreset` |
| `/AIHL/source/particle <particleName>` | `SourceManager::SetParticle` |
| `/AIHL/source/energy <value unit>` | `SourceManager::SetMonoEnergy` |
| `/AIHL/source/point <x y z unit>` | `SourceManager::SetPointPosition` |
| `/AIHL/source/direction <x y z>` | `SourceManager::SetDirection` |
| `/AIHL/source/isotropic` | `SourceManager::SetIsotropic` |
| `/AIHL/source/planeBeam ...` | `SourceManager::SetPlaneBeam` |
| `/AIHL/source/print` | `SourceManager::PrintSummary` |
| `/AIHL/source/reset` | `SourceManager::ResetGPS` |

说明：
- Messenger 只解析命令并转发，不保存 source 业务状态。
- 原生 `/gps/...` 命令没有被屏蔽，仍可直接用于高级 GPS 配置。

### SimulationManager 集成

新增接口：
- `SourceManager* GetSourceManager()`
- `const SourceManager* GetSourceManager() const`
- `std::unique_ptr<PrimaryGeneratorAction> CreatePrimaryGeneratorAction() const`

生命周期：
- `SimulationManager` 持有 `SourceManager` 和 `SourceMessenger`。
- `CreatePrimaryGeneratorAction()` 返回新的 `PrimaryGeneratorAction(sourceManager_.get())`，供后续 `ActionInitialization` 或 `main.cc` 转交给 Geant4 生命周期。

RunSummary 字段：
- `source_configured`
- `source_particle`
- `source_energy`
- `source_preset`

------

## Physics 模块

模块职责：提供基础版 Geant4 physics 配置闭环。`PhysicsFactory` 统一处理别名和 constructor 创建；`PhysicsManager` 保存业务状态；`PhysicsList` 是 Geant4 正式物理入口；`PhysicsMessenger` 提供 `/AIHL/physics/...` 命令并只转发给 manager。

依赖约束：
- 可依赖 `ConfigManager`、`UnitParser`、`BiasingManager`。
- 不依赖 DetectorConstruction、GeometryManager、SourceManager、ScoringManager。
- 不直接创建几何，不绑定 SD，不启动 run。

### PhysicsFactory

位置：
- 头文件：`include/Physics/PhysicsFactory.hh`
- 源文件：`src/Physics/PhysicsFactory.cc`

主要类型：
- `enum class PhysicsCategory`
- `class PhysicsFactory`

| 接口 | 基本作用 |
|---|---|
| `NormalizeOptionName(option)` | 将用户别名归一化为 Geant4 constructor 名称。 |
| `Classify(canonicalName)` | 返回 EM / Hadronic / Elastic / Ion / Decay / Stopping / Optical / Biasing 等分类。 |
| `IsKnownOption(option)` | 判断 option 是否可识别。 |
| `CreatePhysicsConstructor(option)` | 创建对应 `G4VPhysicsConstructor`。 |
| `AvailableAliases()` | 返回可用别名列表。 |

说明：
- `AddHadronicOption`、`AddOtherOption` 不复制别名 if/else，统一走 `PhysicsFactory`。

### PhysicsManager

位置：
- 头文件：`include/Physics/PhysicsManager.hh`
- 源文件：`src/Physics/PhysicsManager.cc`

类：`PhysicsManager`

| 接口 | 基本作用 |
|---|---|
| `SetEMOption/GetEMOption` | 管理电磁物理选项，默认 `G4EmStandardPhysics_option4`。 |
| `AddPhysicsModule/RemovePhysicsModule/ClearPhysicsModules` | 管理额外 physics module。 |
| `AddHadronicOption/AddOtherOption` | 语义封装，内部仍统一走 `AddPhysicsModule`。 |
| `GetPhysicsModules/HasPhysicsModule` | 查询 module 列表。 |
| `SetDefaultCut/GetDefaultCut` | 管理全局 production cut，默认 1 mm。 |
| `SetParticleCut/GetParticleCut/GetParticleCuts` | 按粒子管理 cut。 |
| `SetRegionCut/GetRegionCuts/HasRegionCuts` | 保存 region cut 配置，第一版主要预留。 |
| `SetBiasingManager/GetBiasingManager` | 接入轻量 BiasingManager 指针，不拥有生命周期。 |
| `EnableBiasingPhysics/IsBiasingPhysicsEnabled` | 控制 generic biasing physics hook。 |
| `LoadFromConfig(const ConfigManager&)` | 读取 `[physics]`、`[physics.cuts]`、`[physics.region.*]`。 |
| `Validate()` | 校验 EM、modules、cut 合法性。 |
| `PrintSummary()` | 打印 physics 配置摘要。 |

### PhysicsList

位置：
- 头文件：`include/Physics/PhysicsList.hh`
- 源文件：`src/Physics/PhysicsList.cc`

类：`PhysicsList : public G4VModularPhysicsList`

| 接口 | 基本作用 |
|---|---|
| `PhysicsList(PhysicsManager*)` | 使用外部 PhysicsManager；不拥有生命周期。 |
| `ConfigureFromManager()` | 注册 EM、modules、biasing hook，一次性配置。 |
| `ConfigureEMPhysics()` | 通过 `PhysicsFactory` 创建并注册 EM physics。 |
| `ConfigureExtraPhysicsModules()` | 注册 manager 中的非 EM modules。 |
| `ConfigureBiasingPhysics()` | 如果启用 biasing，则注册 `G4GenericBiasingPhysics` hook；真实 BiasingXS / MultiParticleXS 后续接入。 |
| `ConstructParticle/ConstructProcess` | Geant4 生命周期入口。 |
| `SetCuts()` | 应用 default cut 与 particle cuts。 |
| `SetDefaultCutValue(cut)` | 校验并转发给 Geant4 基类。 |
| `SetParticleCut(particleName, cut)` | 调用 Geant4 `SetCutValue`。 |

说明：
- Region-specific cuts 当前保存在 `PhysicsManager`；若 VolumeBuilder 已经为 `G4Region` 设置 `G4ProductionCuts`，PhysicsList 第一版不重复设置。

### PhysicsMessenger

位置：
- 头文件：`include/Physics/PhysicsMessenger.hh`
- 源文件：`src/Physics/PhysicsMessenger.cc`

命令前缀：`/AIHL/physics/`

| 命令 | 转发到 |
|---|---|
| `/AIHL/physics/setEM <option>` | `PhysicsManager::SetEMOption` |
| `/AIHL/physics/addModule <option>` | `PhysicsManager::AddPhysicsModule` |
| `/AIHL/physics/removeModule <option>` | `PhysicsManager::RemovePhysicsModule` |
| `/AIHL/physics/clearModules` | `PhysicsManager::ClearPhysicsModules` |
| `/AIHL/physics/addHadronic <option>` | `PhysicsManager::AddHadronicOption` |
| `/AIHL/physics/addOther <option>` | `PhysicsManager::AddOtherOption` |
| `/AIHL/physics/setDefaultCut <value unit>` | `PhysicsManager::SetDefaultCut` |
| `/AIHL/physics/setCut <particle> <value unit>` | `PhysicsManager::SetParticleCut` |
| `/AIHL/physics/setRegionCut <region> <particle> <value unit>` | `PhysicsManager::SetRegionCut` |
| `/AIHL/physics/enableBiasing <true|false>` | `PhysicsManager::EnableBiasingPhysics` |
| `/AIHL/physics/verbose <level>` | `PhysicsManager::SetVerboseLevel` |
| `/AIHL/physics/print` | `PhysicsManager::PrintSummary` |

### SimulationManager 集成

新增接口：
- `PhysicsManager* GetPhysicsManager()`
- `const PhysicsManager* GetPhysicsManager() const`
- `std::unique_ptr<G4VModularPhysicsList> CreatePhysicsList() const`

生命周期：
- `SimulationManager` 持有 `PhysicsManager` 和 `PhysicsMessenger`。
- `PhysicsManager` 持有 `BiasingManager*` 非拥有指针。
- Manual 模式下，`CreatePhysicsList()` 返回新的自定义 `PhysicsList(physicsManager_.get())`。
- Reference 模式下，`CreatePhysicsList()` 通过 `PhysicsFactory::CreateReferencePhysicsList(referenceName)` 返回 Geant4 reference physics list，并追加 `extraModules`、generic biasing hook 和 cuts。
- 返回对象供 main.cc 交给 Geant4 RunManager。

RunSummary 字段：
- `physics_mode`
- `physics_reference`
- `physics_extra_modules`
- `physics_em`
- `physics_modules`
- `physics_default_cut`
- `physics_biasing_enabled`

### Physics 第二版补充

模式：
- Manual 模式：`referenceListName` 为空；使用 `emOption + modules` 手动组装 physics constructors。
- Reference 模式：`referenceListName` 非空；通过 `G4PhysListFactory` 创建 Geant4 reference physics list，再追加 `extraModules`、cuts 和 generic biasing hook。

PhysicsManager 新增接口：
- `SetReferenceList(referenceName)`
- `GetReferenceList()`
- `HasReferenceList()`
- `ClearReferenceList()`
- `SetBaseReferenceList(baseName)`
- `GetBaseReferenceList()`
- `SetRequestedEMOption(option)`
- `GetRequestedEMOption()`
- `IsReferenceMode()`
- `IsManualMode()`
- `AddExtraModule(option)`
- `RemoveExtraModule(option)`
- `ClearExtraModules()`
- `HasExtraModule(option)`
- `GetExtraModules()`
- `SetReferenceEMOption(emOption)`
- `BuildReferenceNameWithEM(baseReference, emOption)`

PhysicsFactory 新增接口：
- `IsKnownReferenceList(referenceName)`
- `AvailableReferenceLists()`
- `AvailableReferenceListsEM()`
- `CreateReferencePhysicsList(referenceName)`
- `RegisterExtraModule(list, option)`
- `RegisterExtraModules(list, options)`
- `StripEMSuffix(referenceName)`
- `ApplyEMSuffixToReference(baseReference, emOption)`
- `NormalizeEMOptionForReference(emOption)`
- `ApplyCuts(list, defaultCut, particleCuts)`

PhysicsMessenger 新增命令：
- `/AIHL/physics/setReferenceList <name>`
- `/AIHL/physics/clearReferenceList`
- `/AIHL/physics/setBaseReferenceList <name>`
- `/AIHL/physics/addExtraModule <option>`
- `/AIHL/physics/removeExtraModule <option>`
- `/AIHL/physics/clearExtraModules`
- `/AIHL/physics/listAvailableReferences`
- `/AIHL/physics/listAvailableEMReferences`

SimulationManager 更新：
- `CreatePhysicsList()` 返回类型改为 `std::unique_ptr<G4VModularPhysicsList>`。
- Reference 模式下调用 `PhysicsFactory::CreateReferencePhysicsList()`。
- Manual 模式下仍返回自定义 `PhysicsList(PhysicsManager*)`。
- RunSummary 新增 `physics_mode`、`physics_reference`、`physics_extra_modules`。

EM reference suffix 映射：
- `option1` / `emv` -> `_EMV`
- `option2` / `emx` -> `_EMX`
- `option3` / `emy` -> `_EMY`
- `option4` / `emz` / `em4` -> `_EMZ`
- `livermore` / `liv` -> `_LIV`
- `penelope` / `pen` -> `_PEN`
- `standard` / `default` -> 无后缀

## Actions 模块

位置：
- 头文件：`include/Actions/`
- 源文件：`src/Actions/`

模块边界：
- `Actions` 负责 Geant4 user action 生命周期入口。
- 不实现 Hits / SensitiveDetector / ParticleHit。
- 不实现 EdepScorer / LETScorer。
- 不直接访问 DetectorConstruction / GeometryRegistry / PhysicsManager / BiasingManager。
- `SteppingAction` 默认不主动 `ScoreHit()`，避免后续与 `SensitiveDetector` 重复记录。

### ActionInitialization

头文件：`include/Actions/ActionInitialization.hh`

公开接口：
- `ActionInitialization(SourceManager* sourceManager, ScoringManager* scoringManager, OutputManager* outputManager)`
- `void BuildForMaster() const`
- `void Build() const`
- `void SetVerboseLevel(int level)`
- `int GetVerboseLevel() const`

生命周期连接：
- `BuildForMaster()` 注册 master `RunAction`。
- `Build()` 注册：
  - `PrimaryGeneratorAction(sourceManager)`
  - `RunAction(scoringManager, outputManager)`
  - `EventAction(scoringManager)`
  - `SteppingAction(scoringManager)`
  - `TrackingAction()`

### RunAction

头文件：`include/Actions/RunAction.hh`

公开接口：
- `RunAction(ScoringManager* scoringManager = nullptr, OutputManager* outputManager = nullptr)`
- `void BeginOfRunAction(const G4Run* run)`
- `void EndOfRunAction(const G4Run* run)`
- `void SetScoringManager(ScoringManager* scoringManager)`
- `ScoringManager* GetScoringManager()`
- `void SetOutputManager(OutputManager* outputManager)`
- `OutputManager* GetOutputManager()`
- `void SetVerboseLevel(int level)`
- `int GetVerboseLevel() const`

行为：
- run begin 时调用 `OutputManager::Initialize()` 和 `ScoringManager::BeginRun(runID)`。
- run end 时调用 `ScoringManager::EndRun(runID)`、`ScoringManager::WriteAll()`、`OutputManager::WriteAllHistograms()`、`OutputManager::WriteRunSummary()`、`OutputManager::Flush()`。

### EventAction

头文件：`include/Actions/EventAction.hh`

公开接口：
- `EventAction(ScoringManager* scoringManager = nullptr)`
- `void BeginOfEventAction(const G4Event* event)`
- `void EndOfEventAction(const G4Event* event)`
- `void SetScoringManager(ScoringManager* scoringManager)`
- `ScoringManager* GetScoringManager()`
- `void SetVerboseLevel(int level)`
- `int GetVerboseLevel() const`

行为：
- event begin 时调用 `ScoringManager::BeginEvent(eventID)`。
- event end 时调用 `ScoringManager::EndEvent(eventID)`。

### SteppingAction

头文件：`include/Actions/SteppingAction.hh`

公开接口：
- `SteppingAction(ScoringManager* scoringManager = nullptr)`
- `void UserSteppingAction(const G4Step* step)`
- `void SetScoringManager(ScoringManager* scoringManager)`
- `ScoringManager* GetScoringManager()`
- `void SetVerboseLevel(int level)`
- `int GetVerboseLevel() const`
- `void EnableStepScoring(bool enable)`
- `bool IsStepScoringEnabled() const`
- `void AddKillVolume(const std::string& volumeName)`
- `void ClearKillVolumes()`
- `bool IsKillVolume(const std::string& volumeName) const`

行为：
- 支持按 pre-step physical volume name kill track。
- `stepScoringEnabled=false` 为默认值。
- 只有显式开启 step scoring 时才构造轻量 `HitRecord` 并调用 `ScoringManager::ScoreHit()`。

### TrackingAction

头文件：`include/Actions/TrackingAction.hh`

公开接口：
- `TrackingAction()`
- `void PreUserTrackingAction(const G4Track* track)`
- `void PostUserTrackingAction(const G4Track* track)`
- `void SetVerboseLevel(int level)`
- `int GetVerboseLevel() const`
- `void EnableTrackLogging(bool enable)`
- `bool IsTrackLoggingEnabled() const`

行为：
- 第一版只提供轻量 track logging hook。
- 不创建或设置自定义 `TrackInformation`。

### SimulationManager 集成

新增接口：
- `std::unique_ptr<ActionInitialization> CreateActionInitialization() const`

所有权：
- `SimulationManager` 不持有 `ActionInitialization`。
- `CreateActionInitialization()` 返回新对象，后续由 main.cc / run setup `release()` 交给 `G4RunManager`。
- `ActionInitialization` 使用 `SourceManager*`、`ScoringManager*`、`OutputManager*` 非拥有指针。

------

## Hits 模块

位置：
- 头文件：`include/Hits/`
- 源文件：`src/Hits/`

模块职责：
- 定义 `ParticleHit`、`ParticleHitCollection`、`SensitiveDetector` 和 `TrackInformation`。
- `SensitiveDetector` 是正式 hit scoring 入口：从 `G4Step` 创建 `ParticleHit`，转换为 `HitRecord`，再调用 `ScoringManager::ScoreHit()`。
- `ParticleHit` 不直接访问 `OutputManager` 或 `ScoringManager`。
- `SensitiveDetector` 不直接写 CSV；文件输出仍由 `ScoringManager` / `OutputManager` 管理。

依赖约束：
- 可依赖 Geant4 hit / SD / track 基础类。
- 可依赖 `Output/OutputRecord.hh` 与 `Scoring/ScoringManager.hh`。
- 不依赖 DetectorConstruction、GeometryManager、BiasingManager、OutputManager。

### ParticleHit

头文件：`include/Hits/ParticleHit.hh`

类：`ParticleHit : public G4VHit`

公开接口：
- `ParticleHit()`
- `ParticleHit(const ParticleHit& other)`
- `ParticleHit& operator=(const ParticleHit& other)`
- `void* operator new(std::size_t)`
- `void operator delete(void* hit)`
- `void Draw()`
- `void Print()`
- `Set/GetEventID`
- `Set/GetTrackID`
- `Set/GetParentID`
- `Set/GetName`
- `Set/GetEdep`
- `Set/GetNdep`
- `Set/GetStepLength`
- `Set/GetFirstPos`
- `Set/GetLastPos`
- `Set/GetMomentumDirection`
- `Set/GetEkin`
- `Set/GetProcess`
- `Set/GetVolume`
- `Set/GetWeight`
- `Set/GetLETcalc`
- `Set/GetLETstep`
- `Set/GetZ`
- `Set/GetA`
- `HitRecord ToHitRecord() const`
- `static ParticleHit* FromStep(const G4Step* step, int eventID = -1)`

说明：
- 使用 `G4ThreadLocal G4Allocator<ParticleHit>`。
- `weight` 默认 `1.0`，`FromStep()` 使用 `track->GetWeight()`。
- `LETcalc` / `LETstep` 第一版保留为 0，供后续 LET scorer 填充。

### ParticleHitCollection

头文件：`include/Hits/ParticleHitCollection.hh`

接口：
- `using ParticleHitCollection = G4THitsCollection<ParticleHit>`
- `std::vector<HitRecord> ConvertToHitRecords(const ParticleHitCollection* collection)`

说明：
- collection 为空时返回空 vector。
- 不依赖 `SensitiveDetector` 或 `ScoringManager`。

### SensitiveDetector

头文件：`include/Hits/SensitiveDetector.hh`

类：`SensitiveDetector : public G4VSensitiveDetector`

公开接口：
- `SensitiveDetector(const G4String& name, ScoringManager* scoringManager = nullptr)`
- `void Initialize(G4HCofThisEvent* hce)`
- `G4bool ProcessHits(G4Step* step, G4TouchableHistory* history)`
- `void EndOfEvent(G4HCofThisEvent* hce)`
- `Set/GetScoringManager`
- `Set/GetVerboseLevel`
- `EnableZeroEdepHits` / `IsZeroEdepHitsEnabled`
- `EnableHitCollection` / `IsHitCollectionEnabled`
- `EnableScoring` / `IsScoringEnabled`
- `GetHitsThisEvent`
- `GetRawEdepThisEvent`
- `GetWeightedEdepThisEvent`
- `GetCollectionName`
- `GetCollectionID`

行为：
- 默认 collection 名称为 `ParticleHits`。
- 默认跳过 zero-edep 且 zero-ndep hit。
- 默认创建 Geant4 hit collection。
- 默认启用 scoring；若 `ScoringManager*` 为空，则只收集 hit collection，不写输出。
- `ProcessHits()` 不调用 `ScoringManager::EndEvent()`，event 生命周期仍由 `EventAction` 管理。

### TrackInformation

头文件：`include/Hits/TrackInformation.hh`

类：`TrackInformation : public G4VUserTrackInformation`

公开接口：
- `TrackInformation()`
- `TrackInformation(const G4Track* track)`
- `void Print() const`
- `Set/GetEventID`
- `Set/GetOriginalTrackID`
- `Set/GetAncestorTrackID`
- `Set/GetParentID`
- `Set/IsPrimary`
- `Set/GetPrimaryParticleName`

说明：
- 第一版只保存 track 附加信息，不强制修改 `TrackingAction`。
- 后续可由 `TrackingAction::PreUserTrackingAction()` attach 到 track，用于 ancestor grouping / ParticleAggregator。

### SimulationManager 集成

新增接口：
- `std::function<G4VSensitiveDetector*()> CreateSensitiveDetectorFactory() const`

行为：
- factory 返回 `new SensitiveDetector("AIHLParticleSD", scoringManager_.get())`。
- `SimulationManager::CreateDetectorConstruction()` 会自动给新建的 `DetectorConstruction` 设置该 factory。
- factory 返回裸指针，由 Geant4 `G4SDManager` 管理 detector 生命周期。

与 Actions 的关系：
- 正式 hit scoring 由 `SensitiveDetector` 调用 `ScoringManager::ScoreHit()`。
- `SteppingAction` 默认不做 step scoring，避免和 SD 重复计分。
