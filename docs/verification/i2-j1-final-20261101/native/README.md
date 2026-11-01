# J1 原生证据候选归档

原件在 [raw-evidence.zip](raw-evidence.zip)，逐件原路径/字节/SHA 在 [manifest.json](manifest.json)。ZIP解包时相对路径即当时仓库内来源，26张PNG全部原字节保留；查看代表图19/20/22/24/25/26可复核材料复位、恢复、fallback、150%真实3D及AI占位。无需把原本机路径视为当前安装路径。

## 最终补验说明（覆盖下方历史待完成状态）

四套host的launch/observations/exit均保留，退出均exit0/close_drained=true；GUI源143份逐件与5fe0a10对应。125%原venv实际3D、System保留K、材料青55到复位紫90、默认布局reset、项目保存、隐藏preview并保存布局均已记录。第二host恢复英文System/K、1440x920及preview隐藏，但误用无PyVista解释器，不计完整3D。第三host实际DPR1.5、screen_fallback、中英文本fallback，不计完整3D。第四host明确原D盘venv、scale1.2实际DPR1.5、restored、中文15体积草图真实3D与AI未执行提示，最终也正常退出。

物理多显示器热插拔未做，不冒称完整多显示器验收。两轮真实run分别完成2M/4M；原输入config/macro、manifest/record、summary/metadata、effective身份、小统计和日志均已保留。4个大event_edep CSV仅在manifest登记实际SHA/大小和未归档事实，不把本包当完整输出树，亦不声称新增物理验证。若需重新核验所有metadata产物，须另取这些原文件；本包不能替代它们。

host脚本保存的是目前实际留存版本：早期launch未记host脚本SHA；旧r2 host SHA 99793f…对应的中间脚本版本未单独留存，不重建伪造。当前r2脚本SHA应与第四host的6f01c2…核对；产品GUI身份由各launch的逐源清单独立证明。

## 历史README原文（当时待完成状态原样保留）

# I2/J1 Windows 原生窗口验收：进行中

## 最终补验记录（2026-11-01，覆盖下方“待完成”状态）

本目录原生范围已完成观察，阶段总门禁仍等待 CI 与归档。全部截图先由 sky 返回并实际观察，再存同一图像；不是只核验路径。四个 host 均自然退出 0，close_drained=true，退出原件保持。主窗口编辑指纹仅在用户级事件数改为 2M、4M 时推进；显示动作不改变配置。保存项目 native-accepted-project.json 不含工作区/主题状态；本机设置独立保存在 settings。

- 08 浅色 K、09 英文 K；10 结果分析预设；11 先保存布局、隐藏结果后恢复已保存布局，实际布局恢复。早期被用户调整的粉色与相机方向不作为 agent 操作证据。
- 12–13：实际 2,000,000 事件运行期间浅 K→深 C；自然完成 2M/2M、退出0、success、单run。revision3 snapshot=bf08341eeea295b18053d12f4b81a68928376e85dc6575dd30d587734ea83525。运行后发生的拖动不计作运行中拖动。
- 14–15：实际 4,000,000 事件运行期间切换运行观察布局；自然完成 4M/4M、退出0、success、单run。revision4 snapshot=d66cfd1733695d14075d5af93b01516a717ca577826e40967bfde3655e508307。真实输入/输出/后端身份由 j1-native-rounds12-review.md/json 独立核验，143 GUI源字节与候选一致；运行完成不是独立物理验证。
- 16：选择 System 后实际解析为浅 K。17：默认布局复位，稳定状态下 Run 按钮可见；切回配置页后 3D 区正常展开。瞬时负dock矩形符合Qt停放，未证实稳定不可达缺陷。
- 18–20：在实际后端导出的2体积视图选择材料 G4_Si，颜色改 #00ffff、不透明度55%，画布实际呈青色；全部复位后回 #8c7bc9、90%。设置控件超时后用新状态证实已经生效，未重复提交。所有显示动作保持 revision4/snapshot。
- 21：保存项目、隐藏3D面板、显式保存本机布局。初次用forward-slash绝对路径被Windows文件对话框判文件名无效；改为backslash后保存成功，未覆盖历史文件。原设置副本 settings-before-restart.ini 保留。
- 22：真实关闭原host后，用 r2 --restore-only（不重新应用夹具、不resize）启动；layout_restore=restored，1440×920、DPR1.25、English/System/K及隐藏3D正确恢复。默认项目demo是正常新会话，不冒称自动恢复原项目。该启动使用系统Python，未提供可选PyVista；此项只证明布局主题恢复。
- 23–24：系统Python加 QT_SCALE_FACTOR=1.2，实际DPR1.5，屏幕签名变化触发 screen_fallback 并回到可见默认布局；英文/中文和文本降级说明可读，颜色控件不冒充有效。没有修改系统DPI设置。
- 25–26：改用原完整依赖 D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe，DPR1.5；真实PyVista在中文界面显示15体积草图，外观控件可见，AI面板可以显示且明确“尚未接入模型，不会执行任务”。草图不证明后端几何或物理正确。该host正常退出0。

host收据：1793538060271063700（主验收）、1793540872178013600（125%重启）、1793540963988159300（150%文本降级）、1793541083619590600（150%完整3D）。四份exit均0且关闭收尾完成。主机只有实际可观察的当前屏幕；未宣称物理多显示器热插拔已经测试。跨屏边界另由布局自动回归覆盖，真实缩放变化已观察。仍有旧页面缓存英文/中文与紧凑区域文案，整体易读性和全面可访问性按F8后续优化，不把本次代表性窗口检查扩大成全页面审美验收。

后续只需对本记录及源身份独审、加入最终证据索引；不重跑已经成功的两次百万事件模拟。

源提交 `5fe0a1052e33c96d033375d0920f29b15d432dcc`。原生 host `out/collab/i2-j1-final-native-host.py` 只初始化 silicon_landau 夹具和独立设置/历史/恢复目录；后续交互经 computer-use 的 node_repl + sky 完成。每 500 ms 的观察器只读配置指纹、版本、布局、主题和运行状态，不驱动交互。完整 GUI 源字节、Qt、PID 在 `*-launch.json`。

当前实际窗口为 1440×920 逻辑像素，DPR 1.25。截图均由原生工具返回后实际观察，再将同一图像归档。此前旧源码窗口已通过文件对话框保存草稿到 `out/collab/i2-j1-native/pre-final-window-project.json`，自然退出 0；未丢弃用户草稿。

已观察：

- `01-baseline.png`：初始浅色 B、配置与 3D 并排，手动刷新后 silicon Pad 草图可见。草图不作为 Geant4 几何或物理验证。
- `02-dark-C.png`：实际切换深色 C，布局和编辑指纹保留。
- `03-floating-preview.png`：3D 面板浮动；随后拖动标题栏，重新停靠为配置/3D 页签。
- `04-orange-opacity45.png`：选择 Pad，将不透明度改为 45%，颜色对话框选择 `#ff5500` 并确认；实际画布呈橙色。
- `05-reset-current.png`：恢复当前对象后颜色为 `#8c7bc9`，不透明度 90%，画布回到紫色。
- `06-running-layout.png`：运行观察预设，配置、3D、底部日志同时可见。
- `07-resized-docks.png`：实际拖动分隔线，配置区域由 620 逻辑宽增至 772，3D 相应变窄。向更窄方向第一次拖动受最小宽度约束，未把该次动作算成功。窄区域保留滚动访问；此截图不证明所有内容同时可见。
- 随后点击日志区关闭按钮，日志隐藏，配置与 3D 高度恢复。只读观察记录保留前后矩形。

以上显示动作期间，编辑 revision 保持 2，快照 SHA256 保持 `c2cc32a266ceadd483891744aed09706c64b101b30b366e4199832ea5480f39e`。这是配置未变的证据，不等于尚未执行的真实模拟验证。

待完成：材料级外观/全部复位，另两布局与保存恢复，K 色板/系统策略/英文，真实模拟中的主题布局切换、结果和自然退出，重启恢复与另一代表性 DPI。当前尚不关闭 J1。

桌面中断事实：用户此前明确允许操作。之后工具检测到用户输入，窗口被最小化；状态读取返回 `window is minimized`，一次恢复返回 `user input was detected in this window; call get_window_state before continuing`。已暂停输入并请用户手动恢复，后台矩阵继续。不将该工具中断视为产品缺陷。

`out/collab/i2-j1-final-native-host-r2.py` 已准备 `--restore-only` 模式：重启时不重新应用向导夹具、不覆盖窗口大小，直接观察产品启动恢复结果；当前未启动，不能将其计划当作完成证据。
