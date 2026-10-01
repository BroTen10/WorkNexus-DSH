/**
 * @worknexus/contracts —— WorkNexus-DSH Host Core 契约包（契约版本 v1）。
 *
 * 八类契约与需求书 §3.2 一一对应：
 *   ① IdentityContext  ② SpaceContext  ③ PermissionPolicy  ④ AuditSink
 *   ⑤ UsageLedger      ⑥ EventBus      ⑦ PluginGovernanceView  ⑧ UpdateManager
 *
 * 契约⑨ `KnowledgeProvider` 为 P3 扩展（T-060），与上面八类同包发布；
 * 契约版本 `1.1.0`（次版本递增，见 `docs/HostCore契约-v1.md` §6 变更留痕）。
 *
 * 交付边界（T-029 派发卡）：
 *  - 本包**只放类型与常量**：不承载企业业务数据、不连控制面、不实现 AgentTransport；
 *  - 企业字段使用 `ent` 前缀独立命名空间，不覆盖官方 `identity` / `credentials` / `api` 语义。
 */

export {
  ENTERPRISE_FIELD_PREFIX,
  HOST_CORE_CONTRACT_VERSION,
  type EnterpriseFieldPrefix,
  type HostCoreContractVersion,
} from './version.js'

export {
  IDENTITY_FIELD_PREFIX,
  PERSONAL_IDENTITY,
  type IdentityContext,
  type RunMode,
} from './identity.js'

export { ROLES, ROLE_RANK, hasAtLeastRole, type Role, type SpaceContext } from './space.js'

export {
  DENY_ALL_POLICY,
  ACTIONS,
  READ_ONLY_FOR_VIEWER_POLICY,
  type Action,
  type PermissionPolicy,
  type ResourceRef,
} from './permission.js'

export { AUDIT_SUMMARY_MAX_LENGTH, summarize, type AuditEvent, type AuditResult, type AuditSink } from './audit.js'

export {
  USAGE_SOURCES,
  deriveTotalTokens,
  type UsageLedger,
  type UsageRecord,
  type UsageRecordSource,
} from './usage.js'

export {
  ENTERPRISE_EVENT_NAMESPACE,
  ENTERPRISE_EVENT_TOPICS,
  assertEnterpriseTopic,
  isEnterpriseTopic,
  type EnterpriseEvent,
  type EnterpriseEventTopic,
  type EventBus,
  type Unsubscribe,
} from './event.js'

export { PERSONAL_MODE_GOVERNANCE, type PluginGovernanceView, type PluginHealth, type PluginState, type PluginView } from './plugin.js'

export {
  type UpdateChannel,
  type UpdateCheckInput,
  type UpdateCheckResult,
  type UpdateManager,
  type UpdateOperationResult,
  type UpdateRollbackResult,
  type UpstreamPin,
} from './update.js'

export {
  KNOWLEDGE_HEALTH_STATES,
  type KnowledgeChunk,
  type KnowledgeConfigValidation,
  type KnowledgeHealth,
  type KnowledgeHealthReport,
  type KnowledgeProvider,
  type KnowledgeRetrieveInput,
} from './knowledge.js'
