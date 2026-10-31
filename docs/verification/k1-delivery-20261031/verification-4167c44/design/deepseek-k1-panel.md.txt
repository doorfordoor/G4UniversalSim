# DeepSeek K1 面板候选与本地修复交付

DeepSeek 请求/返回模型均为 `deepseek-flash`，请求 ID `ebf75eb6-18d8-4035-a250-1dd0ba8ac8a7`。原始响应保留在 `out/collab/k1-deepseek-response.json`；原候选存在缺少 `_render_state`、错误 ui_text 签名、层级标题未赋值、小宽度隐藏科学状态四项问题，不能将原响应视为已验收代码。

本地修复保留快照/四层验证、动作网格和历史表格总体布局及 action_requested 信号模式。四层简要状态常显，快照详情和历史默认折叠，最大高度 300，按按钮实际宽度换列，超出内容滚动访问；原生 palette。set_state/set_busy/retranslate_ui 接口保留。动作常量同步加入 import/environment/cancel；cancel 沿用空闲可点、忙时唯一可点的语义。面板只渲染控制器给定快照，四层独立，不推断物理正确。

全部文案改用实际 ui_text/ui_format；精确英文源消息到中文的集中词条移交、接口说明、证据摘要与文件 SHA256 见 [修复写者交付](20261031-k1-panel-delivery.md)。修复交付已随仓库保存；文内 out 日志路径仍指原始本地证据，不作为配置导出包资源声明。

首次专项 766 个 v3 断言入口通过时，27 项中文词条尚未加入，实际使用英语回退；此前不能称其覆盖完整中文布局。主代理补齐词条后，原专项失败于标签右边界超出 viewport，原失败证据 `out/collab/k1-panel-integrated.log` 未改写。

续修确认中文缩列后滚动区仍保留旧 426 像素内容宽度；现通过 Qt 动态尺寸约束与同步布局激活修复。原 60 个 assert 表达式全部保留，增加中文词条存在/不回退/包含中文及内容宽度检查；重复收缩扩张 640→480→360→480→640→360。最新专项退出 0，1598 个 v3 断言入口；compileall 退出 0。新日志分别为 `out/collab/k1-panel-zh-layout-fixed.log` 和 `out/collab/k1-panel-zh-layout-compileall.log`，初次通过日志也保留原字节。RunPage 已由主代理接入，集中词典已补齐；本轮仅做 offscreen 自动验证，未观察实际窗口、未完成控制器端到端验收或 Geant4/物理比较。

本轮仅修复写者交付，无提交。独立复审另派；主代理继续负责动作接线、测试登记、实际窗口与整阶段验收。
