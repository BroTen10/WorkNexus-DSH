/**
 * 官方 session 投影到用量记录：缺失字段一律 null，不推算、不填 0。
 */

import type { UsageRecord, UsageRecordSource } from '@worknexus/contracts'

export type DshUsageProjection = {
  usageId?: string
  sessionId?: string | null
  userId: string
  organizationId: string
  spaceId?: string | null
  pluginId?: string | null
  provider: string
  model: string
  promptTokens?: number | null
  completionTokens?: number | null
  totalTokens?: number | null
  estimatedCost?: number | null
  precise?: boolean
}

export type ProjectedUsageRecord = Omit<UsageRecord, 'usageId' | 'timestamp'>

function nullIfMissing(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function nullIfMissingText(value: string | null | undefined): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

export function toUsageRecord(input: DshUsageProjection): ProjectedUsageRecord {
  const source: UsageRecordSource = input.precise === false ? 'adapter_estimate' : 'dsh_event'
  const promptTokens = nullIfMissing(input.promptTokens)
  const completionTokens = nullIfMissing(input.completionTokens)
  const explicitTotal = nullIfMissing(input.totalTokens)
  const totalTokens = explicitTotal ?? (
    promptTokens !== null && completionTokens !== null ? promptTokens + completionTokens : null
  )
  return {
    organizationId: input.organizationId,
    spaceId: nullIfMissingText(input.spaceId),
    userId: input.userId,
    sessionId: nullIfMissingText(input.sessionId),
    pluginId: nullIfMissingText(input.pluginId),
    provider: input.provider,
    model: input.model,
    promptTokens,
    completionTokens,
    totalTokens,
    estimatedCost: typeof input.estimatedCost === 'number' && Number.isFinite(input.estimatedCost)
      ? input.estimatedCost
      : null,
    source,
  }
}
