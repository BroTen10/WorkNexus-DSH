/**
 * 企业入口挂载 —— 按**运行模式**门控（T-024）。
 *
 * 硬约束：
 *  - 入口注册必须走运行模式判定；**没有模式上下文时按 `personal` 处理**（裁决：模式上下文 T-035 才落地）；
 *  - P1 只交付个人模式，因此**四个企业入口必须隐藏且不报错**（需求书 §3.5 规则 5、§4.1.4 第 1 条）；
 *  - 不新增插件管理 IPC、不使用官方未提供的通道（T-002 §4 N-3；T-004 E-4）；
 *  - 入口的注册/注销与插件启停联动（插件禁用后入口同步消失）。
 */

import type { RunMode } from '@worknexus/contracts'

export type EnterpriseEntryId = 'ent-admin' | 'ent-knowledge' | 'ent-docgraph' | 'ent-ipd'

export type EnterpriseEntry = {
  id: EnterpriseEntryId
  /** 官方 Web 侧栏展示名（中文标签；实现时为 i18n key） */
  label: string
  /** 归属插件（用于启停联动）；P1 未打包任何入口插件，故此字段为计划值 */
  ownerPlugin: string
  /** 是否随发行版预置（Host Core 相关入口为 true） */
  preinstalled: boolean
}

/** 四个企业入口的注册表（需求书 §3.4 白名单类别④）。 */
export const ENTERPRISE_ENTRIES: readonly EnterpriseEntry[] = Object.freeze([
  { id: 'ent-admin', label: '企业管理', ownerPlugin: '@worknexus/ent-admin', preinstalled: false },
  { id: 'ent-knowledge', label: '知识库', ownerPlugin: '@worknexus/ent-knowledge', preinstalled: false },
  { id: 'ent-docgraph', label: 'DocGraph', ownerPlugin: '@worknexus/ent-docgraph', preinstalled: false },
  { id: 'ent-ipd', label: 'IPD', ownerPlugin: '@worknexus/ent-ipd', preinstalled: false },
])

export type RunModeContext = {
  /** 是否已登录企业账号 */
  signedIn?: boolean
  /** 已选定的组织；未选定视为没有组织上下文 */
  organizationId?: string | null
}

/**
 * 运行模式判定（需求书 §3.5）：
 * 企业模式 = 已登录 **且** 已选定组织；其余一律个人模式。
 * 不提供手工强制开关；缺少上下文按 `personal` 处理。
 */
export function resolveRunMode(context?: RunModeContext): RunMode {
  if (!context?.signedIn) return 'personal'
  const org = context.organizationId
  return typeof org === 'string' && org.length > 0 ? 'enterprise' : 'personal'
}

/** 某运行模式下可见的入口 id 列表。个人模式返回空数组（不是 null、不抛错）。 */
export function visibleEntriesFor(mode: RunMode): readonly EnterpriseEntryId[] {
  return mode === 'enterprise' ? ENTERPRISE_ENTRIES.map((e) => e.id) : []
}

/** 宿主侧入口容器（官方 UI 槽位的抽象；不涉及任何官方 IPC）。 */
export interface EntryHost {
  add(entry: EnterpriseEntry): void
  remove(id: EnterpriseEntryId): void
  list(): readonly EnterpriseEntryId[]
}

/** 内存实现，供测试与 P1 的空实现使用。 */
export function createMemoryEntryHost(): EntryHost {
  const present = new Map<EnterpriseEntryId, EnterpriseEntry>()
  return {
    add(entry) {
      present.set(entry.id, entry)
    },
    remove(id) {
      present.delete(id)
    },
    list() {
      return [...present.keys()]
    },
  }
}

/**
 * 按运行模式同步入口：企业模式注册四个入口，个人模式全部注销。
 * 返回本次的增删结果，便于审计与断言。幂等：重复调用不产生重复注册。
 */
export function syncEnterpriseEntries(
  host: EntryHost,
  mode: RunMode,
): { added: EnterpriseEntryId[]; removed: EnterpriseEntryId[] } {
  const want = new Set(visibleEntriesFor(mode))
  const have = new Set(host.list())
  const added: EnterpriseEntryId[] = []
  const removed: EnterpriseEntryId[] = []

  for (const entry of ENTERPRISE_ENTRIES) {
    if (want.has(entry.id) && !have.has(entry.id)) {
      host.add(entry)
      added.push(entry.id)
    } else if (!want.has(entry.id) && have.has(entry.id)) {
      host.remove(entry.id)
      removed.push(entry.id)
    }
  }
  return { added, removed }
}

/** 插件启停事件的最小形态（由官方 plugin manager 事件投影而来，只读）。 */
export type PluginLifecycleEvent = {
  pluginId: string
  state: 'enabled' | 'disabled' | 'uninstalled'
}

/**
 * 入口与插件启停联动：插件被禁用/卸载时，其拥有的入口一并注销；
 * 重新启用时按当前运行模式恢复。
 * 注意：本函数**不改变插件状态**——官方 plugin manager 仍是唯一权威。
 */
export function applyPluginLifecycle(
  host: EntryHost,
  mode: RunMode,
  event: PluginLifecycleEvent,
): { added: EnterpriseEntryId[]; removed: EnterpriseEntryId[] } {
  const owned = ENTERPRISE_ENTRIES.filter((e) => e.ownerPlugin === event.pluginId)
  if (event.state === 'enabled') return syncEnterpriseEntries(host, mode)

  const removed: EnterpriseEntryId[] = []
  for (const entry of owned) {
    if (host.list().includes(entry.id)) {
      host.remove(entry.id)
      removed.push(entry.id)
    }
  }
  return { added: [], removed }
}
