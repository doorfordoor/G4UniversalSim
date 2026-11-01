# I2：离线规划、用户前缀安装与独立卸载

本服务可以在没有 Qt、Geant4 或编译器的 Python 环境中导入。规划只读取明确选择的清单、路径状态和磁盘空间，不联网、创建目录或启动后端。安装只操作显式选定根目录中的**新子目录**，不修改系统 PATH、注册表、已有 Geant4 环境或编译器。

## 真实产物清单

`build_install_catalog.py` 对实际 ZIP / tar.gz 逐文件计算大小和 SHA256，记录精确版本、平台、架构、profile、来源及包内许可文本。清单的 `reviewed: true` 是发布者的明确声明，不是签名。SHA256 只说明字节一致，不证明来源真实性。

清单与它引用的压缩包一起搬移。相邻或下层文件使用相对引用；`load_catalog()` 以**当前清单文件所在目录**为锚点读取，拒绝 `..`、链接和目录逃逸。不要把旧构建机的绝对路径当作可携带交付。

```powershell
python packaging/build_install_catalog.py --archive out/runtime.zip `
  --profile runtime --platform windows --architecture x86_64 --version 1.0.0 `
  --origin "实际构建记录或上游来源" --license-path THIRD_PARTY_NOTICES.md `
  --license-expression LicenseRef-Bundled-Notices --license-source "包内第三方许可目录" `
  --entrypoints '{"backend":"bin/G4UniversalSim.exe"}' --output out/runtime.catalog.json
```

产物中的 `files` 是完整真实清单；不能用示例散列、未知大小或尚不存在的下载地址补齐。安装服务拒绝链接、特殊文件、路径逃逸、大小写冲突、跨 artifact 文件冲突和许可清单缺损。

## 规划与执行

先创建调用者选定的根目录。下面的 `C:/Users/me/Applications` 必须已经存在，而 `G4UniversalSim` 子目录必须不存在。

```powershell
python packaging/install_plan.py --output plan.json plan `
  --catalog runtime.catalog.json --profile runtime --platform windows `
  --architecture x86_64 --version 1.0.0 `
  --prefix C:/Users/me/Applications/G4UniversalSim --allowed-root C:/Users/me/Applications
python packaging/install_plan.py --output install-receipt.json execute --plan plan.json
```

Linux 对应使用 `--platform linux` 和绝对 POSIX 路径。规划可以针对另一个平台，实际执行必须与本机平台/架构一致。Windows 使用系统独占重命名，Linux 使用 `renameat2(RENAME_NOREPLACE)`；文件系统不支持时明确失败，不退回会覆盖空目录的普通 rename。WSL 验证应选择原生 Linux 文件系统前缀，不能假设 `/mnt/c` 支持同样的发布操作。

运行版不要求编译器。`status=published` 只说明安装文件完成发布；环境和运行能力仍由现有 I1 服务重新发现，模拟完成和物理验证是独立证据。

HTTPS artifact 必须由实际已审阅的大小、散列和文件清单描述；执行时再显式添加 `--allow-download`。下载限制 HTTPS，拒绝降级或含凭据的重定向，临时下载完成后先核完整 archive，再逐文件核提取内容。失败的部分文件不会被当作已经核验的缓存。

## 数据与 SDK

`build_data_artifact.py` 读取真实 `--check-geant4-data` 收据，从已选定的数据目录构建独立 artifact，并保留上游 README/限制及来源。canonical 文件夹名来自后端，不能把 conda 数据别名当作 Windows/Linux 通用目录。合并进 runtime 清单后，安装事务生成指向此次新前缀的 `bin/geant4-data.txt`；收据分别保留原模板 SHA 和生成后的 SHA。不会把一个已有目录的存在当作数据内容的物理验证。

`build_sdk_package.py` 打包实际头文件、开发库、G4UniversalSim 后端源码和编译检查项目。SDK 清单明确要求用户选择可用的 CMake 与编译器；服务不会擅自安装系统编译器。安装 SDK 文件不等于编译通过。

```powershell
python packaging/install_plan.py --output sdk-probe.json probe-sdk `
  --prefix C:/Users/me/Applications/G4UniversalSimSDK `
  --build-directory C:/Users/me/Applications/sdk-check `
  --cmake "C:/Program Files/CMake/bin/cmake.exe" --generator "Visual Studio 18 2026"
```

检查项目真实配置、编译、链接并执行 Geant4 API，每条命令、退出码和完整日志单独保存；运行阶段仅使用安装内 SDK 和系统运行库搜索路径。此检查不运行模拟、不验证物理模型。Linux 可选择 `--generator Ninja` / `--compiler /usr/bin/c++`；匹配的开发依赖路径来自 SDK 清单。

## 取消、重启与卸载

同一前缀的执行、恢复、核验、SDK 编译和卸载共用跨进程 OS 锁。另一个操作明确返回 `operation_busy`。锁是前缀旁的小文件，卸载后仍保留，防止删除锁 inode 造成并发失效；它不会进入系统服务或开机启动。

取消或发布前失败会保留归属明确的暂存事务。`inspect_transaction(prefix, allowed_root=...)` 可以在新进程读取已验证原计划；它不自动继续。新日志可显式恢复，旧日志缺少原计划时明确只能清理。

```powershell
python packaging/install_plan.py execute --plan plan.json --resume
python packaging/install_plan.py recover --prefix C:/Users/me/Applications/G4UniversalSim --allowed-root C:/Users/me/Applications
python packaging/install_plan.py verify --prefix C:/Users/me/Applications/G4UniversalSim
python packaging/install_plan.py uninstall --prefix C:/Users/me/Applications/G4UniversalSim
```

发布后的清理失败保持 `published_with_warning`，不会把成功发布改写成失败。恢复能完成 prepared 收据或清理同一事务，同时保留已发布的环境。卸载先核对完整清单和文件 SHA；未知文件、用户添加的目录、修改过的文件或链接会拒绝删除。卸载清理失败会返回带 transaction_id 的 recovery_path，可用 `recover --action uninstall --transaction-id ...` 清理同一已核验事务，不触及其他环境。

包内 `python/G4USimPython(.exe)` 可以执行受信的辅助脚本、`-c` 和 `-m`，并包含 numpy/uproot/awkward 的实际运行依赖；它不是代码执行沙箱。它禁止自动写 `.pyc`，使正常辅助脚本导入不污染安装清单。支持范围须由包自身的 ROOT/CSV 读取、ROOT 写入回读和冻结 GUI 启动收据证明。

## 冻结程序的来源

Windows 冻结使用所选 Python 与系统目录组成的子进程搜索路径，随后审计实际二进制来源，防止其他桌面工具的同名 DLL 混入。GUI 与辅助 Python 的冻结目录带 `g4usim-freeze.json`，记录本次源文件及产物字节；冻结中源文件变化会拒绝发布。该收据是本机构建证据，不是发布者数字签名。

`--reuse-gui` / `--reuse-python-helper` 复用前必须核对当前源码、平台、3D 档位和完整产物清单，复制后再次核对。没有该收据的旧包应重新冻结，不能只用自检能启动来证明它对应当前源码。清理前先检查复用目录与目标的关系；复用默认冻结输出时保留其构建目录。
