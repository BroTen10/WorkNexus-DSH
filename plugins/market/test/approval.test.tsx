/**
 * T-102：安装审批提示与模式差异（§3.5）。
 */

import { describe, expect, it } from 'vitest'

import { APPROVAL_ACTION_LABELS, buildApprovalPrompt, isEnterpriseWhitelistEnforced } from '../src/approval.js'

describe('market approval prompt', () => {
  it('blocks enterprise installs that are not whitelisted', () => {
    const prompt = buildApprovalPrompt({
      pluginId: 'unknown.plugin',
      version: '1.0.0',
      action: 'install',
      mode: 'enterprise',
      whitelisted: false,
    })
    expect(prompt.status).toBe('not-whitelisted')
    expect(prompt.detail).toContain('未通过白名单不能安装')
    expect(isEnterpriseWhitelistEnforced('enterprise')).toBe(true)
  })

  it('records personal-mode requests without enforcing the whitelist', () => {
    const prompt = buildApprovalPrompt({
      pluginId: 'third.party.plugin',
      version: '1.0.0',
      action: 'install',
      mode: 'personal',
      whitelisted: false,
    })
    expect(prompt.status).toBe('recorded-only')
    expect(prompt.detail).toContain('仅被记录')
    expect(isEnterpriseWhitelistEnforced('personal')).toBe(false)
  })

  it('shows allowed state for whitelisted plugins and never claims an official dialog', () => {
    const prompt = buildApprovalPrompt({
      pluginId: 'worknexus.knowledge',
      version: '1.0.0',
      action: 'update',
      mode: 'enterprise',
      whitelisted: true,
    })
    expect(prompt.status).toBe('allowed')
    expect(prompt.surface).toBe('enterprise-ui')
    expect(APPROVAL_ACTION_LABELS.update).toBe('更新')
  })
})
