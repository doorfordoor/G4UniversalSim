# G4UniversalSim 安装包说明

本包含有 G4UniversalSim 后端（`bin/G4UniversalSim.exe`，含所需的 Geant4 11.3.2 与 Xerces-C 动态库和 VC++ 运行库）、图形界面（`gui/G4UniversalSimGUI.exe`，无需另装 Python）、示例配置、场景包与中文文档。

## 需要已有的 Geant4 数据

本包**不含** Geant4 物理数据（约 3 GB）。请先在本机安装 Geant4 11.3 的数据集（G4EMLOW8.6.1、PhotonEvaporation6.1、RadioactiveDecay6.1.2、G4PARTICLEXS4.1、G4ENSDFSTATE3.0 为必需；高精度中子物理另需 G4NDL4.7.1 等），然后任选一种方式告诉程序数据位置：

1. 安装程序中“Geant4 数据文件夹”一页填写的目录（写入 `bin\geant4-data.txt`）；
2. 便携版中直接编辑 `bin\geant4-data.txt`，加入一行数据文件夹路径；
3. 设置环境变量 `GEANT4_DATA_DIR`（或 Geant4 自身的 `G4LEDATA` 等变量，优先于前两种方式）。

检查：在命令行运行 `bin\G4UniversalSim.exe --check-geant4-data`，输出每个数据集的位置；`required_complete` 为 `true` 时即可运行。数据集版本必须与 Geant4 11.3.2 对应（文件夹名需完全一致）。

## 使用

- 图形界面：运行 `gui\G4UniversalSimGUI.exe`（安装版在开始菜单）。后端路径会自动指向本包的 `bin\G4UniversalSim.exe`；运行包默认写到“文档\G4UniversalSim\gui_runs”。
- 命令行：`bin\G4UniversalSim.exe --config <主配置.ini> --macro <宏.mac>`，详见 `docs\中文使用手册.md`。
- 场景包（`scenarios\`）的生成与分析脚本、合并与 JSON 导出需要本机安装 Python 3（`python` 在 PATH 中，或设置 `G4USIM_PYTHON` 指向 python.exe）。

## 许可

第三方组件及其许可见 `THIRD_PARTY_NOTICES.md` 与 `licenses\`。
