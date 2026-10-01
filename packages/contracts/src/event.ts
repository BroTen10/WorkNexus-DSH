/**
 * EventBus —— 契约⑥：企业事件通道。
 *
 * 硬约束（需求书 §3.2 + 总览 §2.1 第 12 条）：
 *  - **复用官方事件机制，不替换官方通道**；
 *  - 企业事件使用独立命名空间 `ent.*`，插件只能订阅**白名单**事件。
 */

export const ENTERPRISE_EVENT_NAMESPACE = 'ent' as const

export const ENTERPRISE_EVENT_TOPICS = Object.freeze([
  'ent.identity.changed',
  'ent.space.switched',
  'ent.audit.written',
  'ent.usage.recorded',
  'ent.plugin.state.changed',
  'ent.update.availability.changed',
] as const)

export type EnterpriseEventTopic = (typeof ENTERPRISE_EVENT_TOPICS)[number]

export type EnterpriseEvent = {
  topic: EnterpriseEventTopic
  occurredAt: string
  actorUserId: string
  organizationId: string
  spaceId?: string | null
  payload: Readonly<Record<string, unknown>>
  /** 事件来源，用于与审计和官方事件分发对齐。 */
  source: string
}

/** 取消订阅函数。 */
export type Unsubscribe = () => void

export interface EventBus {
  publish(event: EnterpriseEvent): Promise<void>
  subscribe(topic: EnterpriseEventTopic, handler: (event: EnterpriseEvent) => void): Unsubscribe
  allowedTopics(): readonly EnterpriseEventTopic[]
}

export function isEnterpriseTopic(value: string): value is EnterpriseEventTopic {
  return (ENTERPRISE_EVENT_TOPICS as readonly string[]).includes(value)
}

/** 事件命名空间校验：企业侧只允许 `ent.*`，防止插件蹭官方通道。 */
export function assertEnterpriseTopic(topic: string): EnterpriseEventTopic {
  if (!isEnterpriseTopic(topic)) {
    throw new Error(`event topic is not in the enterprise whitelist: ${topic}`)
  }
  return topic
}
