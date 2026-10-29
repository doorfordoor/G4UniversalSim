# Stable generated-package startup API

from g4usim_gui.history.run_package_actions import read_generated_run_settings
result = read_generated_run_settings(package_dir)

返回frozen GeneratedRunSettings，字段threads:int、seed:int|None、run_name:str。只读，不分配目录、不改任何项目/控件/文件。使用完整标准包验证（含共享load_project_snapshot的nested metadata规则），再仅从本包当前main.ini严格唯一字段读取这三个值；不采用snapshot陈旧flat或runSettings参数。

threads必须声明、完整ASCII十进制，兼容正号/前导零，范围1..2147483647（是现有后端int32范围，GUI仍另行按实际控件guard）；缺失/空/0/负数/小数/指数/溢出/NBSP拒绝。seed缺失返回None；显式0/负0合法且返回0，显式空/非法/负数/溢出拒绝。name缺失或ASCII空值为空；按INI先去#或;注释、ASCII trim，保留Unicode文本/内部空格/尾NBSP，不继承当前name。frontend seed赋值必须用None判断，不能用seed or空丢失显式0。

duplicate_package在分配新包前会调用同一run参数检查，所以后端非法threads/seed不留新复制目录。frontend仍应按新副本helper结果对齐候选flat与runSettings，再guard再发布；它可以先读旧源preflight以提早发现GUI范围，但新副本读取才是实际命令依据。除三字段之外不建立任意INI反向导入，不重写其他物理配置。

正式底层test_duplicate_generated_package新增：当前main手改2/+007/handwritten current name而snapshot仍threads1；helper及真实副本只认当前main；seed0/-0/INT_MAX/5000前导零正例；seed/name省略返回None/空；name尾NBSP保留；必须threads缺失、空/小数/指数/越界、seed非法等31类准备期拒绝。所有失败不分配复制目录、源包hash不变。helper不会访问GUI current对象；current状态保护由frontend专项独立验证。

component最新证据out/verification/e6-duplicate-settings-component；backend最新证据out/verification/e6-duplicate-settings-backend（Inspect+2完成事件）。不声称新的helper验证物理正确性。
