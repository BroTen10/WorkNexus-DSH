import { describe, expect, it } from 'vitest'

import { buildOfficialSessionHeaders, createIdentityProvider, type IdentityApi, type SecureStore } from '../src/identity.js'

class MemoryStore implements SecureStore {
  private value: string | null = null
  get(): Promise<string | null> { return Promise.resolve(this.value) }
  set(token: string): Promise<void> { this.value = token; return Promise.resolve() }
  remove(): Promise<void> { this.value = null; return Promise.resolve() }
}

function unreachableApi(): IdentityApi {
  return {
    async refresh() { throw new Error('ECONNREFUSED') },
    async login() { throw new Error('ECONNREFUSED') },
  }
}

function expiringApi(): IdentityApi {
  let count = 0
  return {
    async refresh(token: string) {
      count += 1
      return { userId: 'u1', email: 'a@b.com', accessToken: `${token}-new-${count}`, refreshToken: 'r2', expiresAt: '2026-09-29T10:00:00Z', organizationId: 'org-1' }
    },
    async login() {
      return { userId: 'u1', email: 'a@b.com', accessToken: 'a1', refreshToken: 'r1', expiresAt: '2026-09-29T09:00:00Z', organizationId: 'org-1' }
    },
  }
}

describe('identity provider', () => {
  it('falls back to personal mode when the control plane is unreachable', async () => {
    const store = new MemoryStore()
    await store.set('existing-refresh-token')
    const provider = createIdentityProvider({ api: unreachableApi(), secureStore: store })
    await expect(provider.refresh()).resolves.toBeUndefined()
    expect(provider.current()?.mode ?? 'personal').toBe('personal')
    expect(provider.notices().map(item => item.message).join()).toMatch(/企业控制面不可达/)
  })

  it('refreshes an expired token before returning identity', async () => {
    const provider = createIdentityProvider({ api: expiringApi(), secureStore: new MemoryStore() })
    await provider.signIn({ email: 'a@b.com', password: 'x' })
    await provider.refresh()
    expect(provider.current()?.userId).toBe('u1')
    expect(provider.current()?.mode).toBe('enterprise')
  })

  it('never requires the enterprise token on official session headers', async () => {
    expect(buildOfficialSessionHeaders({})).toEqual({})
    expect(buildOfficialSessionHeaders({ Authorization: 'Bearer enterprise' })).toEqual({})
  })
})
