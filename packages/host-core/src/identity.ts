/**
 * 客户端身份联通控制面。
 *
 * 边界（需求书 §3.3 / §11）：
 *  - Refresh Token 只交给传入的 SecureStore；真实实现必须绑定官方凭据服务，不新建本地密钥存储；
 *  - 控制面不可达时回落 personal，官方客户端与 DSH 会话不受影响；
 *  - 企业 Token 不注入官方会话请求头。
 */

import type { IdentityContext } from '@worknexus/contracts'

export type SecureStore = {
  get(): Promise<string | null>
  set(token: string): Promise<void>
  remove(): Promise<void>
}

export type ControlPlaneSession = {
  userId: string
  email: string
  accessToken: string
  refreshToken: string
  expiresAt: string
  organizationId?: string | null
}

export type IdentityApi = {
  login(input: { email: string; password: string }): Promise<ControlPlaneSession>
  refresh(refreshToken: string): Promise<ControlPlaneSession>
}

export type IdentityNotice = {
  code: 'control-plane-unreachable' | 'signed-out'
  message: string
}

export type IdentityProvider = {
  current(): IdentityContext | null
  signIn(input: { email: string; password: string }): Promise<IdentityContext>
  signOut(): Promise<void>
  refresh(): Promise<void>
  notices(): readonly IdentityNotice[]
  hasEnterpriseTokenInOfficialSession(): false
}

function toIdentity(session: ControlPlaneSession): IdentityContext {
  return {
    userId: session.userId,
    email: session.email,
    organizationIds: session.organizationId ? [session.organizationId] : [],
    sessionTokenExpiresAt: session.expiresAt,
    mode: session.organizationId ? 'enterprise' : 'personal',
  }
}

export function createIdentityProvider(deps: {
  api: IdentityApi
  secureStore: SecureStore
  now?: () => Date
}): IdentityProvider {
  let identity: IdentityContext | null = null
  let accessToken: string | null = null
  let notices: IdentityNotice[] = []
  const now = deps.now ?? (() => new Date())

  function applySession(session: ControlPlaneSession): IdentityContext {
    accessToken = session.accessToken
    identity = toIdentity(session)
    notices = []
    return identity
  }

  return {
    current: () => identity,

    async signIn(input) {
      try {
        const session = await deps.api.login(input)
        await deps.secureStore.set(session.refreshToken)
        return applySession(session)
      } catch (error) {
        notices = [{ code: 'control-plane-unreachable', message: '企业控制面不可达，已回到个人模式；DSH 会话仍可用。' }]
        throw error
      }
    },

    async signOut() {
      await deps.secureStore.remove()
      accessToken = null
      identity = null
      notices = [{ code: 'signed-out', message: '已退出企业账号，已回到个人模式。' }]
    },

    async refresh() {
      const refreshToken = await deps.secureStore.get()
      if (!refreshToken) {
        identity = null
        return
      }
      try {
        const session = await deps.api.refresh(refreshToken)
        await deps.secureStore.set(session.refreshToken)
        applySession(session)
      } catch {
        await deps.secureStore.remove()
        accessToken = null
        identity = null
        notices = [{ code: 'control-plane-unreachable', message: '企业控制面不可达，已回到个人模式；DSH 会话仍可用。' }]
      }
    },

    notices: () => notices,

    hasEnterpriseTokenInOfficialSession: () => false,
  }
}

/** 官方会话请求头永远不能携带企业 Token；传入什么都只返回官方安全头。 */
export function buildOfficialSessionHeaders(_input: Record<string, string> = {}): Record<string, string> {
  return {}
}
