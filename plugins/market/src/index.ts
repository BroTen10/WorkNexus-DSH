import { MarketPage } from './pages/Market.js'
import { OFFICIAL_MANAGER_FACTS, type OfficialPluginManagerPort } from './official-manager.js'

export const MARKET_PAGES = Object.freeze([MarketPage])

export {
  OFFICIAL_INSTALL_SPEC_KINDS,
  OFFICIAL_MANAGER_FACTS,
  OFFICIAL_MANAGER_PACKAGE,
  OFFICIAL_MANAGER_UI,
  type OfficialBundleSummary,
  type OfficialInstallRequest,
  type OfficialInstallResult,
  type OfficialInstallSpecKind,
  type OfficialInspectResult,
  type OfficialPluginManagerPort,
} from './official-manager.js'

export { MARKET_ACTIONS, MarketPage } from './pages/Market.js'
export { OFFICIAL_MANAGER_FACTS as marketFacts }

export {
  PRIVATE_SOURCE_DEFAULT_TIMEOUT_MS,
  createPrivateSource,
  type PrivateSource,
  type PrivateSourceConfig,
  type PrivateSourceFetchLike,
  type PrivateSourceListing,
  type PrivateSourcePlugin,
} from './registry/private-source.js'

export {
  APPROVAL_ACTION_LABELS,
  buildApprovalPrompt,
  isEnterpriseWhitelistEnforced,
  type ApprovalAction,
  type ApprovalPrompt,
  type ApprovalPromptInput,
} from './approval.js'

export {
  RiskDisplay,
  assessRisk,
  type PluginRiskInfo,
  type PluginSource,
  type RiskAssessment,
  type RiskLevel,
} from './risk-display.js'

/** 只做只读探测：把官方管理器的可用性暴露给企业 UI，不代理任何安装动作。 */
export function describeMarket(): {
  officialPackage: string
  officialUi: string
  approvalSurface: 'control-plane'
} {
  return {
    officialPackage: OFFICIAL_MANAGER_FACTS.package,
    officialUi: OFFICIAL_MANAGER_FACTS.ui,
    approvalSurface: 'control-plane',
  }
}

export type { OfficialPluginManagerPort as MarketManagerPort }
