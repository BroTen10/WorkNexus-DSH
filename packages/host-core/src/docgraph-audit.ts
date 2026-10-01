/**
 * DocGraph 审计与用量的事件形状（T-074）。
 *
 * 只做**纯函数构造**：不连控制面、不落盘、不发 HTTP。
 * 契约约束（T-009 §5、需求书 §6.2/§6.3）：
 *  - 审计事件记录 `remote_task_id` 与 `contract_id`，用于跨系统对账；
 *  - 用量缺失字段一律 `null`，`source` 只能是 `adapter_estimate`（DocGraph 无用量端点）；
 *  - 不记录正文与 Token 原值。
 */

export const DOCGRAPH_AUDIT_ACTIONS = Object.freeze([
  'docgraph.submit',
  'docgraph.view',
  'docgraph.cancel',
  'docgraph.result',
] as const)

export type DocGraphAuditAction = (typeof DOCGRAPH_AUDIT_ACTIONS)[number]

export type DocGraphAuditInput = {
  action: DocGraphAuditAction
  jobId: string
  organizationId: string
  spaceId: string
  userId: string
  remoteTaskId?: string | null
  contractId?: string | null
  detail?: string
}

export type DocGraphAuditEvent = {
  action: DocGraphAuditAction
  resourceType: 'background_job'
  resourceId: string
  organizationId: string
  spaceId: string
  userId: string
  result: 'success' | 'denied'
  summary: string
  entRemoteTaskId: string | null
  entContractId: string | null
}

export type DocGraphUsageInput = {
  jobId: string
  organizationId: string
  spaceId: string
  userId: string
  mode: 'analysis' | 'review'
  estimatedCost?: number | null
}

export type DocGraphUsageRecord = {
  usageId: string
  pluginId: 'docgraph'
  provider: 'docgraph'
  model: string
  organizationId: string
  spaceId: string
  userId: string
  promptTokens: null
  completionTokens: null
  totalTokens: null
  estimatedCost: number | null
  source: 'adapter_estimate'
}

const RESULT_LABELS: Record<DocGraphAuditAction, string> = {
  'docgraph.submit': '提交 DocGraph 任务',
  'docgraph.view': '查看 DocGraph 任务',
  'docgraph.cancel': '取消 DocGraph 任务',
  'docgraph.result': '查看 DocGraph 结果',
}

export function buildDocGraphAuditEvent(
  input: DocGraphAuditInput,
  result: 'success' | 'denied' = 'success',
): DocGraphAuditEvent {
  const detail = input.detail ? `；${input.detail}` : ''
  return {
    action: input.action,
    resourceType: 'background_job',
    resourceId: input.jobId,
    organizationId: input.organizationId,
    spaceId: input.spaceId,
    userId: input.userId,
    result,
    summary: `${RESULT_LABELS[input.action]} ${input.jobId}${detail}`.slice(0, 200),
    entRemoteTaskId: input.remoteTaskId ?? null,
    entContractId: input.contractId ?? null,
  }
}

/** DocGraph 没有用量端点 → 令牌字段一律为 null，来源固定为 `adapter_estimate`（§2.1 第 15 条）。 */
export function buildDocGraphUsageRecord(input: DocGraphUsageInput): DocGraphUsageRecord {
  return {
    usageId: `docgraph:${input.jobId}`,
    pluginId: 'docgraph',
    provider: 'docgraph',
    model: `docgraph-${input.mode}`,
    organizationId: input.organizationId,
    spaceId: input.spaceId,
    userId: input.userId,
    promptTokens: null,
    completionTokens: null,
    totalTokens: null,
    estimatedCost: typeof input.estimatedCost === 'number' ? input.estimatedCost : null,
    source: 'adapter_estimate',
  }
}
