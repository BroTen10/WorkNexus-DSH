import { describe, expect, it } from 'vitest'

import {
  controlPlaneConnectionAllowed,
  createModeContext,
  dataOwnership,
  enterpriseEntryVisible,
  pluginGovernanceStrength,
  type ModeProviderState,
} from '../src/mode.js'

const signedInOrg: ModeProviderState = {
  signedIn: true,
  organizationId: 'org-1',
  organizationContextValid: true,
  controlPlaneReachable: true,
}

describe('mode determination', () => {
  it('defaults to personal when signed-in state or organization context is absent', () => {
    expect(createModeContext({ signedIn: false, organizationId: null }).mode).toBe('personal')
    expect(createModeContext({ signedIn: false, organizationId: 'org-1' }).mode).toBe('personal')
    expect(createModeContext({ signedIn: true, organizationId: null }).mode).toBe('personal')
    expect(createModeContext({ signedIn: true, organizationId: '' }).mode).toBe('personal')
  })

  it('enters enterprise only after sign-in and organization selection', () => {
    const context = createModeContext(signedInOrg)
    expect(context.mode).toBe('enterprise')
    expect(context.degraded).toBe(false)
    expect(context.notices).toEqual([])
  })

  it('has no manual mode override in the provider state or context API', async () => {
    const state: ModeProviderState = { ...signedInOrg }
    expect('forceMode' in state).toBe(false)
    expect('mode' in state).toBe(false)
    const mod = await import('../src/mode.js')
    expect(Object.keys(mod)).not.toContain('forceMode')
    expect(Object.keys(mod)).not.toContain('setMode')
  })
})

describe('mode gates', () => {
  it('hides enterprise entries and never connects the control plane in personal mode', () => {
    const context = createModeContext({ signedIn: false, organizationId: null })
    expect(enterpriseEntryVisible(context)).toBe(false)
    expect(controlPlaneConnectionAllowed(context)).toBe(false)
    expect(pluginGovernanceStrength(context)).toBe('record-only')
    expect(dataOwnership(context)).toBe('local')
  })

  it('exposes enterprise gates only in healthy enterprise mode', () => {
    const context = createModeContext(signedInOrg)
    expect(enterpriseEntryVisible(context)).toBe(true)
    expect(controlPlaneConnectionAllowed(context)).toBe(true)
    expect(pluginGovernanceStrength(context)).toBe('strict')
    expect(dataOwnership(context)).toBe('organization')
  })
})

describe('mode switching', () => {
  it('is a pure projection and never rolls back or deletes official session/workspace data', async () => {
    const state = Object.freeze({ ...signedInOrg })
    const enterprise = createModeContext(state)
    const personalState = Object.freeze({ ...state, signedIn: false, organizationId: null })
    const personal = createModeContext(personalState)
    expect(enterprise.mode).toBe('enterprise')
    expect(personal.mode).toBe('personal')
    expect(state.signedIn).toBe(true)
    expect(state.organizationId).toBe('org-1')
    const mod = await import('../src/mode.js')
    expect(Object.keys(mod)).not.toContain('rollbackOfficialData')
    expect(Object.keys(mod)).not.toContain('deleteOfficialData')
  })
})

describe('degradation', () => {
  it('keeps the official client available when the control plane is unreachable', () => {
    const context = createModeContext({ ...signedInOrg, controlPlaneReachable: false })
    expect(context.mode).toBe('enterprise')
    expect(context.degraded).toBe(true)
    expect(context.degradationReason).toBe('control-plane-unreachable')
    expect(context.notices.join()).toMatch(/企业控制面不可达/)
    expect(enterpriseEntryVisible(context)).toBe(false)
    expect(controlPlaneConnectionAllowed(context)).toBe(false)
    expect(pluginGovernanceStrength(context)).toBe('record-only')
    expect(context.capabilities.officialSessionAvailable).toBe(true)
  })

  it('falls back to personal when the organization context is invalid', () => {
    const context = createModeContext({ ...signedInOrg, organizationContextValid: false })
    expect(context.mode).toBe('personal')
    expect(context.degraded).toBe(true)
    expect(context.degradationReason).toBe('organization-context-invalid')
    expect(context.notices.join()).toMatch(/组织上下文失效/)
    expect(enterpriseEntryVisible(context)).toBe(false)
    expect(controlPlaneConnectionAllowed(context)).toBe(false)
    expect(dataOwnership(context)).toBe('local')
  })

  it('treats unknown control-plane state as fail-closed enterprise degradation', () => {
    const context = createModeContext({ ...signedInOrg, controlPlaneReachable: undefined })
    expect(context.mode).toBe('enterprise')
    expect(context.degraded).toBe(true)
    expect(context.degradationReason).toBe('control-plane-unreachable')
    expect(enterpriseEntryVisible(context)).toBe(false)
    expect(context.capabilities.officialSessionAvailable).toBe(true)
  })

  it('does not degrade ordinary personal mode', () => {
    const context = createModeContext({ signedIn: false, organizationId: null })
    expect(context.degraded).toBe(false)
    expect(context.degradationReason).toBeNull()
    expect(context.capabilities.officialSessionAvailable).toBe(true)
  })
})
