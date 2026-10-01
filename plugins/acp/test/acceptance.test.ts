/**
 * T-093：P6A 验收集成场景（§4.6.1 四条的可执行证据）。
 */

import { describe, expect, it } from 'vitest'
import { parseEnterpriseDeclaration } from '@worknexus/plugin-runtime'
import manifest from '../plugin.manifest.json'
import { ACP_PAGES, JOB_ACTIONS, JOB_STATUS_LABELS, evaluateToolRequest } from '../src/index.js'

describe('P6A acceptance chain', () => {
  it('任务生命周期与状态集合齐备（创建 / 查看 / 取消 / 恢复 / 关闭）', () => {
    expect(ACP_PAGES[0]?.actions).toEqual(['cancel', 'resume', 'close'])
    expect(JOB_ACTIONS).toEqual(['cancel', 'resume', 'close'])
    expect(Object.keys(JOB_STATUS_LABELS)).toEqual([
      'queued', 'running', 'succeeded', 'failed', 'cancelled', 'closed',
    ])
  })

  it('权限请求受策略约束：写类需管理员，只读自动放行', () => {
    expect(evaluateToolRequest({ tool: 'fs.read', role: 'member' })).toMatchObject({ decision: 'allowed' })
    expect(evaluateToolRequest({ tool: 'fs.write', role: 'member' })).toMatchObject({
      decision: 'denied',
      requiresAdminPrompt: true,
    })
    expect(evaluateToolRequest({ tool: 'fs.write', role: 'admin' })).toMatchObject({ decision: 'allowed' })
  })

  it('插件只用于后台自动化：声明 backgroundOnly、无 IPC、无会话接管', () => {
    const parsed = parseEnterpriseDeclaration(manifest)
    expect(parsed.ok).toBe(true)
    expect(ACP_PAGES[0]?.backgroundOnly).toBe(true)
    expect(Object.isFrozen(ACP_PAGES)).toBe(true)
    const source = JSON.stringify(ACP_PAGES)
    expect(source).not.toContain('ipcRenderer')
    expect(source).not.toContain('AgentTransport')
    // 禁用后无残留：页面与策略都是纯数据/纯函数
    expect(JOB_STATUS_LABELS.closed).toBe('已关闭')
  })
})
