/**
 * T-092：ACP 权限请求策略（与控制面同形）。
 */

import { describe, expect, it } from 'vitest'

import {
  AcpApprovalPrompt,
  POLICY_ADMIN_REQUIRED_TOOLS,
  evaluateToolRequest,
} from '../src/approval.js'

describe('acp tool policy', () => {
  it('auto-allows read-only tools for every role', () => {
    for (const role of ['owner', 'admin', 'member', 'viewer'] as const) {
      expect(evaluateToolRequest({ tool: 'fs.read', role })).toMatchObject({
        decision: 'allowed',
        decidedBy: 'policy',
      })
    }
  })

  it('requires admin confirmation for write-class tools', () => {
    expect(POLICY_ADMIN_REQUIRED_TOOLS).toContain('fs.write')
    expect(evaluateToolRequest({ tool: 'fs.write', role: 'member' })).toMatchObject({
      decision: 'denied',
      reason: 'requires_admin_approval',
      requiresAdminPrompt: true,
    })
    expect(evaluateToolRequest({ tool: 'fs.write', role: 'admin' })).toMatchObject({
      decision: 'allowed',
      decidedBy: 'admin',
    })
    expect(evaluateToolRequest({ tool: 'fs.write', role: 'owner' })).toMatchObject({ decision: 'allowed' })
  })

  it('defaults to deny for unknown tools and never claims an official dialog', () => {
    expect(evaluateToolRequest({ tool: 'unknown.tool', role: 'owner' })).toMatchObject({
      decision: 'denied',
      reason: 'policy.default_deny',
    })
    expect(AcpApprovalPrompt).toMatchObject({
      surface: 'enterprise-ui',
      officialDialogAvailable: false,
    })
  })
})
