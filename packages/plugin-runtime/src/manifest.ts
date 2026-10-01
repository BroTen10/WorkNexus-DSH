/**
 * 企业插件声明：官方 bundle/package 声明 + 企业侧治理扩展。
 *
 * 规范边界（需求书 §5.2 / 总览 §2.1 第 13 条）：
 *  - 不提供第二套插件装载器或生命周期；
 *  - 官方字段原样保留（如 `dsh.bundle.patch`、依赖关系）；
 *  - 企业扩展字段只由企业侧读取，官方不理解也不会导致声明失效；
 *  - 权限枚举直接来自 `@worknexus/contracts` 的 `Action`。
 */

import { ACTIONS, HOST_CORE_CONTRACT_VERSION, type Action } from '@worknexus/contracts'
import { satisfies, validRange } from 'semver'
import { z } from 'zod'

export type EnterprisePluginType = 'ui' | 'dsh' | 'service' | 'governance' | 'composite'

export type GovernanceSource = 'private-registry' | 'official' | 'local'

export type GovernanceApproval = 'required' | 'none'

export type OfficialBundleDeclaration = {
  dependencies?: Record<string, string>
  optionalDependencies?: Record<string, string>
  peerDependencies?: Record<string, string>
  dsh?: {
    bundle?: {
      patch?: string
    }
  }
}

export type EnterpriseDeclaration = OfficialBundleDeclaration & {
  id: string
  name: string
  version: string
  type: EnterprisePluginType
  dshCompatibility: string
  hostCoreCompatibility: string
  protected: boolean
  permissions: PluginPermission[]
  uiSlots: string[]
  governance: {
    source: GovernanceSource
    approval: GovernanceApproval
  }
}

/**
 * 需求书 §5.2 样例中的 `identity.read` 是企业管理插件的最小读取权限，
 * T-030 契约未列出；本包将其作为插件声明扩展动作处理，不改 Host Core 契约版本。
 */
export type PluginPermission = Action | 'identity.read'

const PLUGIN_PERMISSIONS = Object.freeze([...ACTIONS, 'identity.read'] as const)

export type EnterpriseDeclarationResult =
  | { ok: true; declaration: EnterpriseDeclaration }
  | { ok: false; problems: string[] }

export type CompatibilityResult = { ok: boolean; problems: string[] }

const actionSchema = z.enum(ACTIONS)

const officialRecord = z.record(z.string(), z.string())

const schema = z.object({
  id: z.string().min(1, 'id must be a non-empty string'),
  name: z.string().min(1, 'name must be a non-empty string'),
  version: z.string().refine((value) => value.trim().length > 0, 'version must be a non-empty string'),
  type: z.enum(['ui', 'dsh', 'service', 'governance', 'composite']),
  dshCompatibility: z.string().refine(
    (value) => validRange(value) !== null,
    'dshCompatibility must be a valid semver range',
  ),
  hostCoreCompatibility: z.string().refine(
    (value) => validRange(value) !== null,
    'hostCoreCompatibility must be a valid semver range',
  ),
  protected: z.boolean(),
  permissions: z.array(
    z.string().refine(
      (value) => (PLUGIN_PERMISSIONS as readonly string[]).includes(value),
      'permission must come from the enterprise permission whitelist',
    ),
  ),
  uiSlots: z.array(z.string().min(1)),
  governance: z.object({
    source: z.enum(['private-registry', 'official', 'local']),
    approval: z.enum(['required', 'none']),
  }),
  dependencies: officialRecord.optional(),
  optionalDependencies: officialRecord.optional(),
  peerDependencies: officialRecord.optional(),
  dsh: z.object({
    bundle: z.object({
      patch: z.string().min(1),
    }).optional(),
  }).optional(),
}).passthrough()

function zodProblems(error: z.ZodError): string[] {
  return error.issues.map((issue) => {
    const path = issue.path.length === 0 ? '<root>' : issue.path.join('.')
    return `${path}: ${issue.message}`
  })
}

/**
 * 解析企业插件声明。官方字段和企业字段都在同一个 `package.json` 级声明上；
 * 本函数只做校验和读取，不装载插件、不改变官方 bundle 生命周期。
 */
export function parseEnterpriseDeclaration(raw: unknown): EnterpriseDeclarationResult {
  const result = schema.safeParse(raw)
  if (!result.success) {
    return { ok: false, problems: zodProblems(result.error) }
  }

  return {
    ok: true,
    declaration: result.data as EnterpriseDeclaration,
  }
}

/**
 * 校验声明与当前 DSH / Host Core 契约版本的兼容性。
 *
 * 注意：官方 plugin-manager 实际使用 `peerDependencies` 做安装和启动预检；
 * `dshCompatibility` 是企业侧的规范语义，企业安装器/审计器必须在官方预检之外复核它。
 */
export function checkCompatibility(
  declaration: EnterpriseDeclaration,
  env: { dshVersion: string; hostCoreVersion: string },
): CompatibilityResult {
  const problems: string[] = []
  if (!satisfies(env.dshVersion, declaration.dshCompatibility)) {
    problems.push(
      `dshCompatibility is not satisfied by DSH ${env.dshVersion} (range: ${declaration.dshCompatibility})`,
    )
  }
  if (!satisfies(env.hostCoreVersion, declaration.hostCoreCompatibility)) {
    problems.push(
      `hostCoreCompatibility is not satisfied by contract ${env.hostCoreVersion} `
        + `(range: ${declaration.hostCoreCompatibility})`,
    )
  }
  return { ok: problems.length === 0, problems }
}

/** Host Core 契约版本的便捷值，供调用方与 T-030 契约版本保持同源。 */
export const CURRENT_HOST_CORE_CONTRACT_VERSION = HOST_CORE_CONTRACT_VERSION
