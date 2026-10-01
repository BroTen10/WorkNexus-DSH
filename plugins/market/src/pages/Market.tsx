/**
 * 企业侧市场入口页面声明（T-100）。
 *
 * 浏览/安装/启停**走官方插件管理器**（`ui-plugin-manager` 侧边栏入口），
 * 企业侧只补白名单、审批、审计与安全提示；不新增插件管理 IPC。
 */

export const MARKET_ACTIONS = Object.freeze(['browse', 'request-install', 'request-enable', 'request-disable'] as const)

export const MarketPage = {
  id: 'browse',
  uiSlot: 'worknexus.market.browse',
  title: '插件市场',
  permission: 'plugin.enable',
  officialSurface: 'ui-plugin-manager',
  actions: MARKET_ACTIONS,
  enterpriseApproval: 'control-plane',
  requiresRiskDisplay: true,
} as const
