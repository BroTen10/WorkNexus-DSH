import { describe, expect, it } from 'vitest'

import { parseEnterpriseDeclaration, checkCompatibility } from '../src/manifest.js'

const minimal = {
  id: 'worknexus.knowledge',
  name: 'Knowledge',
  version: '1.0.0',
  type: 'service',
  dshCompatibility: '>=0.2.0-rc.1 <0.3.0',
  hostCoreCompatibility: '>=1.0.0',
  protected: false,
  permissions: ['kb.retrieve', 'space.read'],
  uiSlots: [],
  governance: {
    source: 'private-registry',
    approval: 'none',
  },
}

describe('parseEnterpriseDeclaration', () => {
  it('accepts a declaration covering the spec field set', () => {
    const result = parseEnterpriseDeclaration(minimal)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.declaration.id).toBe('worknexus.knowledge')
      expect(result.declaration.type).toBe('service')
      expect(result.declaration.protected).toBe(false)
      expect(result.declaration.permissions).toEqual(['kb.retrieve', 'space.read'])
    }
  })

  it('keeps official bundle fields and lets them coexist with enterprise-only fields', () => {
    const result = parseEnterpriseDeclaration({
      ...minimal,
      description: 'Official bundle declaration with enterprise governance fields',
      dependencies: {
        '@deepseek-ai/dsh-time-context': 'workspace:*',
      },
      peerDependencies: {
        '@deepseek-ai/cordis': 'workspace:~',
      },
      dsh: {
        bundle: {
          patch: './cordis.patch.yml',
        },
      },
    })
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.declaration.dsh?.bundle?.patch).toBe('./cordis.patch.yml')
      expect(result.declaration.peerDependencies?.['@deepseek-ai/cordis']).toBe('workspace:~')
    }
  })

  it('preserves protected=true as an enterprise-side governance signal', () => {
    const result = parseEnterpriseDeclaration({ ...minimal, protected: true })
    expect(result.ok).toBe(true)
    if (result.ok) expect(result.declaration.protected).toBe(true)
  })

  it('rejects an unknown permission', () => {
    const result = parseEnterpriseDeclaration({ ...minimal, permissions: ['root.everything'] })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.problems.join()).toMatch(/permissions/)
  })

  it('rejects an unsupported governance source or approval mode', () => {
    for (const governance of [
      { source: 'manual', approval: 'none' },
      { source: 'official', approval: 'automatic' },
    ]) {
      const result = parseEnterpriseDeclaration({ ...minimal, governance })
      expect(result.ok).toBe(false)
      if (!result.ok) expect(result.problems.join()).toMatch(/governance/)
    }
  })
})

describe('checkCompatibility', () => {
  it('accepts compatible DSH and Host Core ranges', () => {
    const parsed = parseEnterpriseDeclaration(minimal)
    if (!parsed.ok) throw new Error('fixture must parse')
    expect(checkCompatibility(parsed.declaration, {
      dshVersion: '0.2.0-rc.1',
      hostCoreVersion: '1.0.0',
    })).toEqual({ ok: true, problems: [] })
  })

  it('rejects a DSH range that excludes the running version', () => {
    const parsed = parseEnterpriseDeclaration(minimal)
    if (!parsed.ok) throw new Error('fixture must parse')
    const result = checkCompatibility(parsed.declaration, {
      dshVersion: '0.3.0',
      hostCoreVersion: '1.0.0',
    })
    expect(result.ok).toBe(false)
    expect(result.problems.join()).toMatch(/dshCompatibility/)
  })

  it('rejects a Host Core range that excludes the contract version', () => {
    const parsed = parseEnterpriseDeclaration(minimal)
    if (!parsed.ok) throw new Error('fixture must parse')
    const result = checkCompatibility(parsed.declaration, {
      dshVersion: '0.2.0-rc.1',
      hostCoreVersion: '0.9.0',
    })
    expect(result.ok).toBe(false)
    expect(result.problems.join()).toMatch(/hostCoreCompatibility/)
  })
})
