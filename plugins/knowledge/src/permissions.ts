/**
 * 知识库插件的权限预判与模式门控。
 *
 * 复用 Host Core 权限枚举（T-044 客户端矩阵），与企业管理插件同源；
 * 客户端判断只用于 UI 预判，最终裁决仍在控制面（`app.services.permission`）。
 */

import { hasAtLeastRole, type SpaceContext } from '@worknexus/contracts'
import { canPermission, type ServerAction } from '@worknexus/host-core'

export type KnowledgePermission = ServerAction

export function canRender(actor: SpaceContext, action: KnowledgePermission): boolean {
  return canPermission(actor, action, { type: 'knowledge', id: actor.organizationId })
}

/** 个人模式零页面（需求书 §3.5、总览 §2.1 第 8 条）。 */
export function visiblePages(mode: 'personal' | 'enterprise'): string[] {
  return mode === 'enterprise' ? [...KNOWLEDGE_PAGE_IDS] : []
}

/**
 * 只有获得授权的管理员角色能看到写操作入口（P3-F09）。
 *
 * 裁决：Host Core 权限矩阵把 `kb.bind` 授予 member（用于空间内自助绑定请求），
 * 但 P3-F09 要求「管理员可配置 Provider、绑定空间、启停知识库」→ 页面级写入口
 * 取「至少 admin」与 `kb.bind` 的**交集**，不修改冻结矩阵本身。
 */
export function canManageKnowledge(actor: SpaceContext): boolean {
  return hasAtLeastRole(actor, 'admin') && canRender(actor, 'kb.bind')
}

const KNOWLEDGE_PAGE_IDS = ['connections', 'admin'] as const
