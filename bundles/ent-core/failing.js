/**
 * @worknexus/ent-core/failing —— **仅用于失败隔离验证**的故意失败插件。
 *
 * 它**不进入** `cordis.patch.yml`，即不会随发行版启用。
 * `scripts/verify_t023_bundle.py` 会在隔离 DSH_HOME 中把一行指向本模块，
 * 用以证明「企业侧插件启动/解析失败不会阻断 Host Core 与其余官方 bundle」。
 */

export const name = 'ent-core-failing'

export function apply() {
  throw new Error('ent-core failing plugin: intentional failure for failure-isolation probe')
}
