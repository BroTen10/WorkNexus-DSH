export {
  CURRENT_HOST_CORE_CONTRACT_VERSION,
  checkCompatibility,
  parseEnterpriseDeclaration,
  type CompatibilityResult,
  type EnterpriseDeclaration,
  type EnterpriseDeclarationResult,
  type EnterprisePluginType,
  type GovernanceApproval,
  type GovernanceSource,
  type OfficialBundleDeclaration,
  type PluginPermission,
} from './manifest.js'

export {
  attachGovernanceHooks,
  createGovernanceHooks,
  type AttachGovernanceHooksDeps,
  type GovernanceAuditEntry,
  type GovernanceAuditHandler,
  type GovernanceDeps,
  type GovernanceHooks,
  type GovernanceInstallDecision,
  type GovernancePluginRef,
  type OfficialPluginManagerChangedEvent,
  type OfficialPluginManagerContext,
} from './governance.js'
