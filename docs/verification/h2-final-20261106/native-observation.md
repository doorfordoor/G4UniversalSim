# H2 Windows 原生计分入口观察

候选 5f68ede07b7da4fa673eafd38532694efdb9c4b0，C独立工作区产品 MainWindow，Qt windows，启动参数、隔离配置见 launch.py。后端选择的独立构建身份 5f68ede07b7da4fa673eafd38532694efdb9c4b0，exe SHA-256 79A9EE218B44BCB9ED5AFFFA9EE34824C629D5701A238BB043BF5E969A4B240B。原生退出会话68505返回0。

实际窗口路径为 配置 → 运行配置 → 计分。关闭临时3D预览停靠区、滚动计分页后，观察到Dose/Fluence/LET过滤及Dose/Fluence动能谱行，含粒子、区间、分箱控件。
1. Dose关闭时勾选Filter dose steps，实际显示 [SCORING][ERROR] dose filter requires [scoring] dose = true。取消后恢复 [SCORING][INFO] OK。
2. Fluence关闭时勾选Kinetic-energy spectrum for fluence，实际显示 [SCORING][ERROR] fluence spectrum requires [scoring] fluence = true。启用Fluence后，原生摘要恢复计分OK。
3. 只在临时demo中操作，关闭时选择丢弃本次未保存修改，进程exit 0。截屏及交互回执在本轮工具记录。首次UIA索引点击因coordinate input geometry unavailable未执行，随后用重新观察的窗口坐标完成操作。

范围是Windows原生入口、前置条件和退出。H2物理运行和GUI模型/输出分别由正式后端与GUI报告证明。右侧字段需横向滚动，中英混排及旧LET提示留作界面文案/布局后续，现有控件和校验可达。
