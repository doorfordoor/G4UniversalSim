# J1 首次3D展示P2修复独立复审（2026-11-01）

结论：本轮P2可关闭。当前补全真实用户激活入口，并在共享auto分支使用脱离业务模型的副本，未发现新增阻断问题。未改布局/预览产品、未跑大矩阵或冻结。

## 源码

- window/workspace_layout.py:99-100及219-227：配置导航、Show3D按钮与菜单toggle-on显式发送用户激活；纯preset/restore/float不因此调度。visibility只处理hidden→停止待发timer，保留手动隐藏语义。
- widgets/config/preview3d.py:111-140：复用原_backend_timer，_building/ready/autoOff/hidden守卫明确；隐藏或关闭auto取消排队；已有1.2s debounce语义保留。MainWindow在构造/恢复结束才ready，未通过强行show全部dock或延时禁输入绕过。
- window/content.py:120-149：auto不再_update_project_from_page_without_preview。ProjectPage.apply_to_project仅读控件写入deepcopy(project)，geometry_settings只构造新GeometrySettings，generated_inputs拿geometry/materials副本；同一geometry_controller.request仍是唯一owner。manual保留原同步入口、inputs工厂与request语义。can_mutate_workspace仅检查fault/busy/closing，无隐式flush。

## 独立复验

原D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe、Qt offscreen：
1. 同原窄反例复跑退出0，首次配置导航timerTrue/export1、旧3D标签随后export2，日志j1-preview-p2-independent-fixed.log。先前首次0/后续1的缺口已补。
2. 独立调用永久preview_activation_cases，真实auto分支只mock最终controller.request，不mock收集路径；真实invalid seed草稿、Project/drafts/geometry/materials/F5 revision/K1 levels与records逐项不变。收集/设置run默认/项目更新保存/runner start/terminate/kill均设置失败哨兵；首次、重显、autoOff、hidden、pure preset/restore/float与旧标签通过。日志j1-preview-p2-independent-readonly.log退出0。

证据更正：原反例脚本把结果写固定j1-layout-review-first-preview-confirmed.json，本次复跑意外覆盖该JSON为修复后1/2；未将覆写文件冒充旧失败。旧首次0的观测仍保留j1-layout-review-first-preview.json、原独审报告与工具回执；旧完整0/1工具回执存在。本次新stdout日志独立保存，writer自己的j1-layout-first-preview-fixed.json也是修复后证据。后续探针应使用唯一输出名。

本结论是激活/只读与无业务副作用的窄复审，不替代root继续native/DPI/真实后端、CI/frozen及完整J1阶段判断。
