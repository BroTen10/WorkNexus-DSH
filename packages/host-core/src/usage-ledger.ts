/**
 * HTTP 用量账本适配：只调用追加 record 与查询接口，不提供更新/删除。
 */

import type { UsageLedger, UsageRecord } from '@worknexus/contracts'

export type UsageHttpResponse = { ok: boolean; status: number }

export type HttpUsageLedgerDeps = {
  endpoint: string
  post: (url: string, body: Omit<UsageRecord, 'usageId' | 'timestamp'>) => Promise<UsageHttpResponse>
  get: (url: string) => Promise<{ ok: boolean; status: number; body?: UsageRecord[] }>
}

export function createHttpUsageLedger(deps: HttpUsageLedgerDeps): UsageLedger {
  return {
    async record(entry) {
      const response = await deps.post(deps.endpoint, entry)
      if (!response.ok) throw new Error(`usage ledger rejected record with HTTP ${response.status}`)
    },
    async query(q) {
      const parts = [
        `organizationId=${encodeURIComponent(q.organizationId)}`,
        `from=${encodeURIComponent(q.from)}`,
        `to=${encodeURIComponent(q.to)}`,
      ]
      if (q.spaceId !== undefined) parts.push(`spaceId=${encodeURIComponent(q.spaceId)}`)
      const response = await deps.get(`${deps.endpoint}?${parts.join('&')}`)
      if (!response.ok) throw new Error(`usage ledger query failed with HTTP ${response.status}`)
      return response.body ?? []
    },
  }
}
