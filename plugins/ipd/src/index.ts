/**
 * IPD Demo 插件入口注册（T-080，需求书 P5-F01）。
 *
 * 入口形态（裁决，见 `docs/IPD入口_T-080.md`）：
 *  - 官方方案要求入口走官方 UI 槽位；`uiSlots` 在冻结的企业声明 schema 里是**字符串槽位**，
 *    因此「菜单入口 / 项目空间入口」由本模块的入口注册表表达，并映射到对应槽位；
 *  - 按 `ModeContext` 门控：个人模式零入口；
 *  - 插件禁用后入口与权限同步注销 —— 注册表是纯数据，注销即移除，无残留全局状态。
 *
 * 明确不做（§4.5.3）：真实 IPD 流程引擎、审批流、PLM/ERP 集成、甘特图排程、复杂表单建模。
 */

import type { SpaceContext } from '@worknexus/contracts'
import { canPermission } from '@worknexus/host-core'

export type IpdEntryKind = 'menu' | 'project-space'

export type IpdEntry = {
  id: string
  kind: IpdEntryKind
  uiSlot: string
  title: string
  permission: 'space.read'
}

export const IPD_ENTRIES: readonly IpdEntry[] = Object.freeze([
  {
    id: 'ipd-menu',
    kind: 'menu',
    uiSlot: 'worknexus.ipd.menu',
    title: 'IPD 示例',
    permission: 'space.read',
  },
  {
    id: 'ipd-process',
    kind: 'project-space',
    uiSlot: 'worknexus.ipd.process',
    title: 'IPD 样例流程',
    permission: 'space.read',
  },
  {
    id: 'ipd-project',
    kind: 'project-space',
    uiSlot: 'worknexus.ipd.project',
    title: 'IPD 样例项目',
    permission: 'space.read',
  },
])

/** 个人模式零入口（§3.5、总览 §2.1 第 8 条）。 */
export function visibleEntries(mode: 'personal' | 'enterprise'): IpdEntry[] {
  return mode === 'enterprise' ? [...IPD_ENTRIES] : []
}

/** 授权成员才可见（P5-F06）：复用 Host Core 权限枚举。 */
export function entriesForActor(actor: SpaceContext, mode: 'personal' | 'enterprise'): IpdEntry[] {
  if (mode !== 'enterprise') return []
  // 无组织上下文（例如未登录/未选定组织）不显示企业入口
  if (typeof actor.organizationId !== 'string' || actor.organizationId.length === 0) return []
  const allowed = canPermission(actor, 'space.read', { type: 'ipd', id: actor.organizationId })
  return allowed ? [...IPD_ENTRIES] : []
}

export const IPD_PAGE_SLOTS = Object.freeze(['worknexus.ipd.process', 'worknexus.ipd.project'])
