/**
 * UpdateManager —— 契约⑧：发行版版本锁定口径、上游跟随策略、差异集状态与 rebase 演练记录。
 *
 * 硬约束（需求书 §3.2）：
 *  - **更新与回滚由官方实现**，本契约不重写更新算法；
 *  - 回滚必须能回到「**最近可用**」版本，而不是只能回到最新版（附录 B T-030 Step 3）。
 */

/** 更新通道 = 官方双 origin 机制（T-007 §3.3）：稳定与灰度各占一个 origin，不新增机制。 */
export type UpdateChannel = 'stable' | 'canary'

export type UpdateCheckInput = {
  currentVersion: string
  channel: UpdateChannel
  /** 官方强更策略给出的强制位，由官方实现提供，本契约只透传。 */
  mandatory: boolean
}

export type UpdateCheckResult = {
  available: boolean
  currentVersion: string
  targetVersion: string | null
  mandatory: boolean
  channel: UpdateChannel
}

export type UpdateOperationResult = {
  ok: boolean
  detail?: string
}

export type UpdateRollbackResult = {
  ok: boolean
  /** 回滚后实际运行的版本（最近可用版本，不一定是最新版本）。 */
  restoredVersion: string
  detail?: string
}

/** 上游跟随与差异集状态（对应 `docs/技术决策-*.md` 与 `patches/`）。 */
export type UpstreamPin = {
  tag: string
  commit: string
  /** 差异集补丁文件名（相对 `patches/`），空表示无差异。 */
  diffsetPatch: string | null
  /** rebase 演练记录（相对 `docs/`），未演练时为 null。 */
  rebaseDrillRecord: string | null
}

export interface UpdateManager {
  check(input: UpdateCheckInput): Promise<UpdateCheckResult>
  download(input: { targetVersion: string }): Promise<UpdateOperationResult>
  install(input: { targetVersion: string }): Promise<UpdateOperationResult>
  rollback(input: { organizationId: string }): Promise<UpdateRollbackResult>
  upstreamPin(): Promise<UpstreamPin>
}
