/**
 * UsageLedger —— 契约⑤：记录 Token、模型、会话、用户、空间、成本等用量。
 *
 * 字段与需求书 §6.3 一一对应。三条硬约束：
 *  1. 无法获得的字段**必须留空**，不允许填假数（§6.3 末句）；
 *  2. `source` 只允许 `dsh_event` / `adapter_estimate` / `manual_import`（总览 §2.1 第 15 条）；
 *  3. 与审计一样**只追加**（§4.2.4），因此本契约只有 `record` 与 `query`。
 */

export type UsageRecordSource = 'dsh_event' | 'adapter_estimate' | 'manual_import'

export const USAGE_SOURCES: readonly UsageRecordSource[] = Object.freeze([
  'dsh_event',
  'adapter_estimate',
  'manual_import',
])

export type UsageRecord = {
  usageId: string
  timestamp: string
  organizationId: string
  spaceId: string | null
  userId: string
  sessionId: string | null
  pluginId: string | null
  provider: string
  model: string
  promptTokens: number | null
  completionTokens: number | null
  totalTokens: number | null
  estimatedCost: number | null
  source: UsageRecordSource
}

export interface UsageLedger {
  record(entry: Omit<UsageRecord, 'usageId' | 'timestamp'>): Promise<void>
  query(q: { organizationId: string; spaceId?: string; from: string; to: string }): Promise<UsageRecord[]>
}

/**
 * 由 prompt/completion 推导 total，二者任一为 null 时返回 null（**不猜**）。
 * 对齐 T-006 §3.3：官方 session 投影可得，但 `estimated_cost` 不可得。
 */
export function deriveTotalTokens(
  promptTokens: number | null,
  completionTokens: number | null,
): number | null {
  if (promptTokens === null || completionTokens === null) return null
  return promptTokens + completionTokens
}
