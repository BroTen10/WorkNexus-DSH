/**
 * 知识库管理页面（T-065，需求书 P3-F09）。
 *
 * 三项能力与 P3-F09 一一对应：配置 Provider、绑定空间、启停知识库。
 * 门控：`ModeContext` = enterprise 才注册（个人模式零入口，§3.5 / 总览 §2.1 第 8 条）；
 * 权限：写操作只对「至少 admin」可见（`canManageKnowledge`，T-061 裁决）。
 *
 * 不新增插件管理 IPC、不引入第二套设计系统；真实渲染由官方 UI 槽位承载（B 类）。
 */

import type { SpaceContext } from '@worknexus/contracts'
import { canManageKnowledge } from '../permissions.js'

export type KnowledgeAdminActionId = 'configure-provider' | 'bind-space' | 'toggle-knowledge'

export type KnowledgeAdminAction = {
  id: KnowledgeAdminActionId
  title: string
  permission: 'kb.bind'
  requiresAdmin: true
}

export const KNOWLEDGE_ADMIN_ACTIONS: readonly KnowledgeAdminAction[] = Object.freeze([
  { id: 'configure-provider', title: '配置 Provider', permission: 'kb.bind', requiresAdmin: true },
  { id: 'bind-space', title: '绑定空间', permission: 'kb.bind', requiresAdmin: true },
  { id: 'toggle-knowledge', title: '启停知识库', permission: 'kb.bind', requiresAdmin: true },
])

export const KnowledgeAdminPage = {
  id: 'admin',
  uiSlot: 'worknexus.knowledge.admin',
  title: '知识库管理',
  permission: 'kb.bind',
  actions: KNOWLEDGE_ADMIN_ACTIONS,
} as const

/** 授权管理员可见的操作集；其他角色（含 viewer/member）为空集。 */
export function adminActionsFor(actor: SpaceContext): KnowledgeAdminAction[] {
  return canManageKnowledge(actor) ? [...KNOWLEDGE_ADMIN_ACTIONS] : []
}
