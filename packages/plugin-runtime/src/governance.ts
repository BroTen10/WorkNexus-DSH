/**
 * 企业治理挂接：订阅官方 plugin-manager 事件，不重写生命周期。
 *
 * 上游事实（dsh-v0.2.0-rc.1）：
 *  - 完成操作统一 emit `plugin-manager/changed`；
 *  - `reason` 只包含 `plugin | bundle | install | remove`；
 *  - 载荷不含插件 id / version，也不区分 enable / disable 方向；
 *  - 企业侧因此把 `plugin` / `bundle` 记录为 `plugin.changed`，不臆造启停方向。
 */

export type GovernancePluginRef = {
  pluginId: string
  version: string
}

export type GovernanceAuditEntry = {
  action: 'plugin.install' | 'plugin.enable' | 'plugin.disable' | 'plugin.uninstall' | 'plugin.changed'
  pluginId: string
  version: string
  result: 'success' | 'failure' | 'denied'
  detail?: string
  source: 'official-plugin-manager'
}

export type GovernanceAuditHandler = (entry: GovernanceAuditEntry) => Promise<void> | void

export type GovernanceDeps = {
  whitelist: readonly string[]
  audit: GovernanceAuditHandler
}

export type GovernanceInstallDecision = {
  decision: 'allow' | 'deny'
  reason?: string
}

export type GovernanceHooks = {
  onInstall(event: GovernancePluginRef): Promise<GovernanceInstallDecision>
  onEnable(event: GovernancePluginRef): Promise<void>
  onDisable(event: GovernancePluginRef): Promise<void>
  onUninstall(event: GovernancePluginRef): Promise<void>
  onPluginOrBundleChanged(event: { reason: 'plugin' | 'bundle' }): Promise<void>
}

export type OfficialPluginManagerChangedEvent = {
  reason: 'plugin' | 'bundle' | 'install' | 'remove'
}

export interface OfficialPluginManagerContext {
  on(
    topic: 'plugin-manager/changed',
    handler: (event: OfficialPluginManagerChangedEvent) => void,
  ): void | (() => void)
}

export type AttachGovernanceHooksDeps = {
  official: OfficialPluginManagerContext
  hooks: GovernanceHooks
  onError?: (error: unknown) => void
}

const UNKNOWN_PLUGIN: GovernancePluginRef = {
  pluginId: '<unknown>',
  version: '<unknown>',
}

function auditEntry(
  action: GovernanceAuditEntry['action'],
  event: GovernancePluginRef,
  result: GovernanceAuditEntry['result'],
  detail?: string,
): GovernanceAuditEntry {
  return detail === undefined
    ? { action, pluginId: event.pluginId, version: event.version, result, source: 'official-plugin-manager' }
    : { action, pluginId: event.pluginId, version: event.version, result, detail, source: 'official-plugin-manager' }
}

/** 创建只读治理钩子；安装判定只回答 allow/deny，启停仍由官方 plugin-manager 执行。 */
export function createGovernanceHooks(deps: GovernanceDeps): GovernanceHooks {
  async function writeAudit(
    event: GovernancePluginRef,
    action: GovernanceAuditEntry['action'],
    result: GovernanceAuditEntry['result'],
    detail?: string,
  ): Promise<void> {
    await deps.audit(auditEntry(action, event, result, detail))
  }

  return {
    async onInstall(event: GovernancePluginRef): Promise<GovernanceInstallDecision> {
      const allowed = deps.whitelist.includes(event.pluginId)
      try {
        await writeAudit(event, 'plugin.install', allowed ? 'success' : 'denied')
      } catch (error) {
        return {
          decision: 'deny',
          reason: error instanceof Error ? error.message : String(error),
        }
      }
      return allowed
        ? { decision: 'allow' }
        : { decision: 'deny', reason: 'plugin is not on the enterprise whitelist' }
    },

    async onEnable(event: GovernancePluginRef): Promise<void> {
      try {
        await writeAudit(event, 'plugin.enable', 'success')
      } catch {
        // 官方启停不得被企业审计失败阻塞。
      }
    },

    async onDisable(event: GovernancePluginRef): Promise<void> {
      try {
        await writeAudit(event, 'plugin.disable', 'success')
      } catch {
        // 官方启停不得被企业审计失败阻塞。
      }
    },

    async onUninstall(event: GovernancePluginRef): Promise<void> {
      try {
        await writeAudit(event, 'plugin.uninstall', 'success')
      } catch {
        // 官方卸载不得被企业审计失败阻塞。
      }
    },

    async onPluginOrBundleChanged(event: { reason: 'plugin' | 'bundle' }): Promise<void> {
      try {
        await writeAudit(UNKNOWN_PLUGIN, 'plugin.changed', 'success', event.reason)
      } catch {
        // 官方变更不得被企业审计失败阻塞。
      }
    },
  }
}

/** 把治理钩子挂到官方 `plugin-manager/changed` 事件；返回取消订阅函数。 */
export function attachGovernanceHooks(deps: AttachGovernanceHooksDeps): () => void {
  const disposer = deps.official.on('plugin-manager/changed', (event) => {
    void (async () => {
      switch (event.reason) {
        case 'install':
          await deps.hooks.onInstall(UNKNOWN_PLUGIN)
          break
        case 'remove':
          await deps.hooks.onUninstall(UNKNOWN_PLUGIN)
          break
        case 'plugin':
        case 'bundle':
          await deps.hooks.onPluginOrBundleChanged({ reason: event.reason })
          break
      }
    })().catch((error) => {
      deps.onError?.(error)
    })
  })

  return () => {
    if (typeof disposer === 'function') disposer()
  }
}
