/**
 * 连接配置页面（T-061 声明，T-065 收口到管理页面）。
 *
 * 只声明页面身份与所需权限；真实渲染由官方 UI 槽位承载（不新增插件管理 IPC）。
 */

export const ConnectionsPage = {
  id: 'connections',
  uiSlot: 'worknexus.knowledge.connections',
  title: '知识库连接',
  permission: 'kb.bind',
} as const
