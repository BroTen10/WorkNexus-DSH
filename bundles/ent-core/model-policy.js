/**
 * @worknexus/ent-core/model-policy —— 企业模型策略（T-025）。
 *
 * 职责边界（P1-F10 / P1-F14 的「我方补充部分」+ T-006 §7 约束 1）：
 *  1. **凭据一律复用官方凭据服务**（`@deepseek-ai/dsh-credentials`）：本模块只接受
 *     「是否存在可用凭据」这一**布尔事实**，既不存储也不读取密钥值；形似密钥的输入一律拒绝。
 *  2. **只做「预置默认 + 可下发清单」**：不接管官方模型配置页面，不注册 UI / IPC / 路由。
 *  3. **策略不可用即回落**：清单为空、默认模型不在清单内、或层结构非法时，回落到官方默认行为，
 *     且 `blocked` 恒为 `false`（**不阻塞会话**）。
 *  4. **零副作用**：不落盘、不联网、不打日志；`describe()` 只返回非敏感摘要。
 *
 * 因此本模块**不是**第二套凭据存储、也**不是**第二套配置中心（T-002 §4 N-7/N-8）。
 */

export const name = 'ent-core-model-policy'

/** 企业模型策略的 schema 版本（与 Host Core 契约版本相互独立）。 */
export const MODEL_POLICY_SCHEMA_VERSION = 1

/** 凭据事实的唯一合法来源标识（官方凭据缝）。 */
export const CREDENTIAL_SOURCE = 'official-credentials-service'

/** 预置默认策略（企业侧默认配置，白名单 5.1；可由 org / space 层下发覆盖）。 */
export const DEFAULT_MODEL_POLICY = Object.freeze({
  schemaVersion: MODEL_POLICY_SCHEMA_VERSION,
  defaultModel: 'deepseek-chat',
  allowedModels: Object.freeze(['deepseek-chat', 'deepseek-reasoner']),
})

/** 允许出现在策略里的层名。 */
const POLICY_LAYERS = ['organization', 'space']

/** 只允许出现在凭据事实里的键；其余键一律拒绝（fail closed）。 */
const CREDENTIAL_FACT_KEYS = ['hasUsableCredential', 'credentialRefs']

const MAX_MODEL_ID_LENGTH = 128
const MAX_CREDENTIAL_REF_LENGTH = 64

/** 形似密钥/令牌的片段：命中即拒绝，避免密钥值被喂进企业侧。 */
const SECRET_LIKE = [
  /sk-[A-Za-z0-9_-]{6,}/u,
  /\bBearer\s+\S+/iu,
  /\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+/iu,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/u,
]

function isPlainObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function looksLikeSecret(text) {
  return SECRET_LIKE.some(pattern => pattern.test(text))
}

function assertNoSecret(value, where) {
  if (typeof value !== 'string') return
  if (looksLikeSecret(value)) {
    throw new Error(`ent-core model policy: ${where} looks like a secret value and is refused`)
  }
}

/**
 * 归一化一个策略层：只接受 `defaultModel` 与 `allowedModels`，其余键拒绝。
 * @param {unknown} layer - org 或 space 层的候选值。
 * @param {string} where - 诊断用的层名。
 * @returns {{ defaultModel?: string, allowedModels?: string[] } | undefined} 归一化结果；未下发时返回 undefined。
 */
function normalizeLayer(layer, where) {
  if (layer === undefined || layer === null) return undefined
  if (!isPlainObject(layer)) throw new Error(`ent-core model policy: ${where} must be an object`)
  for (const key of Object.keys(layer)) {
    if (key !== 'defaultModel' && key !== 'allowedModels') {
      throw new Error(`ent-core model policy: ${where} has unsupported key "${key}"`)
    }
  }
  const out = {}
  const { defaultModel, allowedModels } = layer
  if (defaultModel !== undefined) {
    if (typeof defaultModel !== 'string' || defaultModel === '' || defaultModel.length > MAX_MODEL_ID_LENGTH
      || /\s/u.test(defaultModel)) {
      throw new Error(`ent-core model policy: ${where}.defaultModel must be a compact model id`)
    }
    assertNoSecret(defaultModel, `${where}.defaultModel`)
    out.defaultModel = defaultModel
  }
  if (allowedModels !== undefined) {
    if (!Array.isArray(allowedModels)) throw new Error(`ent-core model policy: ${where}.allowedModels must be an array`)
    out.allowedModels = allowedModels.map((entry) => {
      if (typeof entry !== 'string' || entry === '' || entry.length > MAX_MODEL_ID_LENGTH || /\s/u.test(entry)) {
        throw new Error(`ent-core model policy: ${where}.allowedModels entries must be compact model ids`)
      }
      assertNoSecret(entry, `${where}.allowedModels`)
      return entry
    })
  }
  return out
}

/**
 * 把官方凭据服务的**只读事实**投影成企业侧唯一允许的凭据输入形态。
 * @param {unknown} input - 形如 `{ hasUsableCredential: boolean, credentialRefs?: string[] }`。
 * @returns {{ hasUsableCredential: boolean, credentialRefs: string[], source: string }} 冻结的只读事实。
 * @throws {Error} 输入含未知键、非布尔值或形似密钥的字符串时抛错（fail closed）。
 */
export function resolveCredentialFact(input) {
  if (input === undefined || input === null) input = {}
  if (!isPlainObject(input)) throw new Error('ent-core model policy: credential fact must be an object')
  for (const key of Object.keys(input)) {
    if (!CREDENTIAL_FACT_KEYS.includes(key)) {
      throw new Error(`ent-core model policy: credential fact must not carry "${key}" (only a boolean fact is allowed)`)
    }
  }
  const { hasUsableCredential, credentialRefs } = input
  if (typeof hasUsableCredential !== 'boolean') {
    throw new Error('ent-core model policy: hasUsableCredential must be a boolean fact')
  }
  let refs = []
  if (credentialRefs !== undefined) {
    if (!Array.isArray(credentialRefs)) throw new Error('ent-core model policy: credentialRefs must be an array of names')
    refs = credentialRefs.map((ref) => {
      if (typeof ref !== 'string' || !/^[A-Za-z_][A-Za-z0-9_]*$/u.test(ref) || ref.length > MAX_CREDENTIAL_REF_LENGTH) {
        throw new Error('ent-core model policy: credentialRefs entries must be POSIX-style names, never values')
      }
      assertNoSecret(ref, 'credentialRefs')
      return ref
    })
  }
  return Object.freeze({
    hasUsableCredential,
    credentialRefs: Object.freeze(refs),
    source: CREDENTIAL_SOURCE,
  })
}

/**
 * 解析企业模型策略：space > organization > 预置默认；再用可用模型清单过滤。
 * 任一环节不可用时**回落官方默认**，`blocked` 恒为 false。
 * @param {object} [input] - 策略输入。
 * @param {object} [input.organization] - 组织层下发（`defaultModel` / `allowedModels`）。
 * @param {object} [input.space] - 空间层下发（同上，优先级最高）。
 * @param {string[]} [input.availableModels] - 官方侧实际可用模型；给出时用于过滤清单。
 * @param {string} [input.officialDefaultModel] - 官方默认模型，回落目标。
 * @returns {object} 冻结的有效策略。
 */
export function resolveModelPolicy(input = {}) {
  if (!isPlainObject(input)) throw new Error('ent-core model policy: input must be an object')
  for (const key of Object.keys(input)) {
    if (key !== 'organization' && key !== 'space' && key !== 'availableModels' && key !== 'officialDefaultModel') {
      throw new Error(`ent-core model policy: unsupported input key "${key}"`)
    }
  }
  const { availableModels, officialDefaultModel } = input
  if (availableModels !== undefined && !Array.isArray(availableModels)) {
    throw new Error('ent-core model policy: availableModels must be an array')
  }
  if (officialDefaultModel !== undefined) assertNoSecret(officialDefaultModel, 'officialDefaultModel')

  const fallback = reason => Object.freeze({
    schemaVersion: MODEL_POLICY_SCHEMA_VERSION,
    source: 'official-default',
    defaultModel: officialDefaultModel ?? null,
    allowedModels: Object.freeze([]),
    blocked: false,
    reason,
  })

  let layers
  try {
    layers = POLICY_LAYERS.map(layer => normalizeLayer(input[layer], layer))
  }
  catch (error) {
    return fallback(`invalid-policy: ${error instanceof Error ? error.message : String(error)}`)
  }

  const [organization, space] = layers
  const effectiveDefault = space?.defaultModel ?? organization?.defaultModel ?? DEFAULT_MODEL_POLICY.defaultModel
  const declared = space?.allowedModels ?? organization?.allowedModels ?? DEFAULT_MODEL_POLICY.allowedModels

  let allowedModels = [...declared]
  if (availableModels !== undefined) {
    const available = new Set(availableModels)
    allowedModels = allowedModels.filter(model => available.has(model))
  }
  allowedModels = [...new Set(allowedModels)]

  if (allowedModels.length === 0) return fallback('no-allowed-model')
  if (!allowedModels.includes(effectiveDefault)) {
    const promoted = [...allowedModels]
    if (typeof officialDefaultModel === 'string' && allowedModels.includes(officialDefaultModel)) {
      return Object.freeze({
        schemaVersion: MODEL_POLICY_SCHEMA_VERSION,
        source: 'enterprise-policy',
        defaultModel: officialDefaultModel,
        allowedModels: Object.freeze(promoted),
        blocked: false,
        reason: 'default-not-allowed: fell back to the official default',
      })
    }
    return Object.freeze({
      schemaVersion: MODEL_POLICY_SCHEMA_VERSION,
      source: 'enterprise-policy',
      defaultModel: allowedModels[0],
      allowedModels: Object.freeze(promoted),
      blocked: false,
      reason: 'default-not-allowed: fell back to the first allowed model',
    })
  }

  return Object.freeze({
    schemaVersion: MODEL_POLICY_SCHEMA_VERSION,
    source: 'enterprise-policy',
    defaultModel: effectiveDefault,
    allowedModels: Object.freeze(allowedModels),
    blocked: false,
    reason: null,
  })
}

/** 非敏感自述：供门禁与企业侧审计读取。 */
export function describe() {
  return {
    ok: true,
    detail: 'enterprise model policy: preset defaults plus a downstream list, no credential storage',
    schemaVersion: MODEL_POLICY_SCHEMA_VERSION,
    defaultModel: DEFAULT_MODEL_POLICY.defaultModel,
    allowedModels: [...DEFAULT_MODEL_POLICY.allowedModels],
    credentialSource: CREDENTIAL_SOURCE,
    storesCredentials: false,
    implementsCredentialStore: false,
    takesOverOfficialModelSettings: false,
    blockedOnPolicyFailure: false,
  }
}

/**
 * Cordis 插件入口：**刻意无副作用**。
 * 不注册服务、不接管官方模型配置、不订阅事件、不落盘——策略只经由
 * `resolveModelPolicy()` 被显式调用，避免任何隐式的全局状态。
 */
export function apply() {}
