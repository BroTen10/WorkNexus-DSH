/**
 * Host Core 契约版本。
 *
 * 口径（总览 §2.1 第 17 条）：破坏性变更 → minor 递增并写迁移说明；新增字段 → patch。
 * 冻结后任何变更必须在 `docs/HostCore契约-v1.md` 留痕（T-034）。
 */

export const HOST_CORE_CONTRACT_VERSION = '1.1.0' as const

/** 契约版本的语义化形式，供运行时校验与 manifest 兼容性判断使用。 */
export type HostCoreContractVersion = typeof HOST_CORE_CONTRACT_VERSION

/**
 * 企业扩展字段的命名空间前缀。
 *
 * 总览 §2.1 第 13 条：企业字段独立命名空间，**不覆盖官方** `identity` / `credentials` / `api` 语义；
 * 必要时加 `ent` 前缀。第三方与本方插件一律通过该前缀读取企业字段。
 */
export const ENTERPRISE_FIELD_PREFIX = 'ent' as const

/** 企业字段前缀的类型别名，供各契约标注键名前缀（等价于字面量 `'ent'`）。 */
export type EnterpriseFieldPrefix = typeof ENTERPRISE_FIELD_PREFIX
