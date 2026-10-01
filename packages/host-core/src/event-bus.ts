/**
 * 企业事件通道：官方 Cordis 事件机制之上的薄适配层。
 *
 * 硬约束（T-033 增补 S1/S2、需求书 §3.2 / §5.1）：
 *  - 所有发布与订阅都转交传入的官方 `Context.emit()` / `Context.on()`；
 *  - 本模块不保存事件、不排队、不维护第二套总线状态；
 *  - 订阅 topic 必须命中契约的 `ent.*` 白名单；
 *  - 单个企业订阅者抛错被隔离，不影响其他订阅者和官方分发。
 */

import {
  assertEnterpriseTopic,
  ENTERPRISE_EVENT_TOPICS,
  type EnterpriseEvent,
  type EnterpriseEventTopic,
} from '@worknexus/contracts'

/** 官方 Cordis `Context` 中企业通道实际需要的最小事件面。 */
export interface OfficialEventContext {
  emit(topic: string, event: EnterpriseEvent): void
  on(topic: string, handler: (event: EnterpriseEvent) => void): void | (() => void)
}

export type EnterpriseEventHandler = (event: EnterpriseEvent) => void

export type EnterpriseEventChannelError = {
  topic: EnterpriseEventTopic
  event: EnterpriseEvent
  error: unknown
}

export type EnterpriseEventChannel = {
  publish(event: EnterpriseEvent): void
  subscribe(topic: string, handler: EnterpriseEventHandler): () => void
  allowedTopics(): readonly EnterpriseEventTopic[]
}

export type CreateEnterpriseEventChannelDeps = {
  official: OfficialEventContext
  onError?: (input: EnterpriseEventChannelError) => void
}

/** 用官方事件机制承载企业事件；`deps.official` 由应用装配时传入。 */
export function createEnterpriseEventChannel(
  deps: CreateEnterpriseEventChannelDeps,
): EnterpriseEventChannel {
  return {
    publish(event: EnterpriseEvent): void {
      assertEnterpriseTopic(event.topic)
      deps.official.emit(event.topic, event)
    },

    subscribe(topic: string, handler: EnterpriseEventHandler): () => void {
      const enterpriseTopic = assertEnterpriseTopic(topic)
      const disposer = deps.official.on(enterpriseTopic, (event) => {
        try {
          handler(event)
        } catch (error) {
          deps.onError?.({ topic: enterpriseTopic, event, error })
        }
      })

      return () => {
        if (typeof disposer === 'function') disposer()
      }
    },

    allowedTopics: () => ENTERPRISE_EVENT_TOPICS,
  }
}
