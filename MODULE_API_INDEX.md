# G4UniversalSim Module API Index

本文档记录已经完成模块中可被后续模块调用的主要类、结构体、函数、文件位置与基本作用。后续每完成一个模块，应追加更新本文件，作为跨模块开发时的接口索引。

约定：

- 路径均相对于项目根目录 `G4UniversalSim/`。
- 本索引只记录稳定的对外接口，不记录内部 helper 函数。
- 若接口行为存在重要约定，例如大小写、默认值、异常行为，应在“说明”中写明。

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
- `SimulationManager` 依赖 `ConfigManager` 与 `OutputManager`，只预留其他 Manager 指针，不实现材料、几何、物理、源、计分、偏置逻辑。
- `AppMessenger` 依赖 Geant4 UI command，但只修改 `SimulationManager` / `SimulationContext`，不直接操作 Detector、Physics、Scoring、Biasing 或 run。

重要约定：

- `SimulationContext` 默认 `outputDir = "output"`、`numThreads = 1`、`interactive = false`、`checkOverlaps = true`、`dryRun = false`。
- seed 为可选状态；调用 `GetSeed()` 前可用 `HasSeed()` 判断。
- `SimulationManager::Initialize()` 执行 `LoadConfig()`、`Configure()`、`BuildManagers()`、初始化 `OutputManager`、写基础 `RunSummary`。
- 尚未实现的 `MaterialManager`、`GeometryManager`、`PhysicsManager`、`SourceManager`、`BiasingManager`、`ScoringManager` 当前 getter 返回 `nullptr`。

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
| `void Configure()` | 从主配置读取 `[run]` 和 `[output]` 基础字段写入 context。 |
| `void BuildManagers()` | 当前构建 ConfigManager / OutputManager，预留其他 manager 接入位置。 |
| `void PrintSummary() const` | 向 `std::cout` 打印当前上下文和状态。 |
| `bool IsConfigured() const` | 查询是否已配置。 |
| `bool IsInitialized() const` | 查询是否已初始化。 |
| `ConfigManager* GetConfigManager()` | 获取 ConfigManager。 |
| `OutputManager* GetOutputManager()` | 获取 OutputManager。 |
| `MaterialManager* GetMaterialManager()` | 预留材料 manager getter，当前可为 `nullptr`。 |
| `GeometryManager* GetGeometryManager()` | 预留几何 manager getter，当前可为 `nullptr`。 |
| `PhysicsManager* GetPhysicsManager()` | 预留物理 manager getter，当前可为 `nullptr`。 |
| `SourceManager* GetSourceManager()` | 预留源 manager getter，当前可为 `nullptr`。 |
| `BiasingManager* GetBiasingManager()` | 预留 biasing manager getter，当前可为 `nullptr`。 |
| `ScoringManager* GetScoringManager()` | 预留 scoring manager getter，当前可为 `nullptr`。 |

说明：

- `Configure()` 读取 `[run] threads`、`seed`、`interactive`、`macro`、`verbose`、`check_overlaps`、`run_name` 以及 `[output] dir`；缺失时使用 `SimulationContext` 默认值。
- `Initialize()` 会创建输出目录并写出 `run_summary.txt`。
- 当前不创建 `G4RunManager`，不注册 Detector、PhysicsList 或 ActionInitialization。

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
