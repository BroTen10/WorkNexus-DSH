/**
 * 企业审计只追加 Sink：控制面生成 eventId / timestamp，客户端不重写事件。
 */

import type { AuditEvent, AuditSink } from '@worknexus/contracts'

export type HttpResponse = { ok: boolean; status: number }

export type HttpAuditSinkDeps = {
  endpoint: string
  post: (url: string, body: Omit<AuditEvent, 'eventId' | 'timestamp'>) => Promise<HttpResponse>
}

export function createHttpAuditSink(deps: HttpAuditSinkDeps): AuditSink {
  return {
    async write(event: Omit<AuditEvent, 'eventId' | 'timestamp'>): Promise<void> {
      const response = await deps.post(deps.endpoint, event)
      if (!response.ok) {
        throw new Error(`audit sink rejected event with HTTP ${response.status}`)
      }
    },
  }
}
