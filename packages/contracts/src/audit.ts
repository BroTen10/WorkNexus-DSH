/**
 * AuditSink —— 契约④：写入操作审计事件。
 *
 * 硬约束（需求书 §4.2.4 + 附录 B Global Constraints 第 3 条）：
 *  - 审计**只追加**，不提供更新/删除；
 *  - 默认**不记录**完整 prompt、完整模型输出、API Key、密码、验证码。
 * 因此本契约只有 `write`，没有 `update` / `delete` / `read`（读走控制面）。
 */

export type AuditResult = 'success' | 'failure' | 'denied'

export type AuditEvent = {
  eventId: string
  timestamp: string
  userId: string
  organizationId: string
  spaceId?: string | null
  action: string
  resourceType: string
  resourceId?: string | null
  result: AuditResult
  device: string
  summary: string
}

export interface AuditSink {
  write(event: Omit<AuditEvent, 'eventId' | 'timestamp'>): Promise<void>
}

/** 审计摘要的字符上限：避免把正文/长文本带进审计（默认最小采集）。 */
export const AUDIT_SUMMARY_MAX_LENGTH = 200

export function summarize(text: string): string {
  const flat = text.replace(/\s+/gu, ' ').trim()
  return flat.length <= AUDIT_SUMMARY_MAX_LENGTH ? flat : `${flat.slice(0, AUDIT_SUMMARY_MAX_LENGTH - 1)}…`
}
