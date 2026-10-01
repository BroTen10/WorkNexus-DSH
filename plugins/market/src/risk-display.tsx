/**
 * 插件安全提示（T-104，需求书 P6B-F06、§4.6.2 验收 3）。
 *
 * 展示：权限清单、来源、风险等级与最近更新时间；风险等级按**三项规则**判定（裁决）：
 *  1. 权限范围：写类/治理类权限越多风险越高；
 *  2. 来源可信度：`local`（本方发行）与 `official` 视为可信，`private-registry` 需企业自评；
 *  3. 最近更新：超过 180 天未更新视为陈旧，风险上调。
 *
 * 不隐藏来源与权限信息（T-104 禁止事项）。
 */

import type { ReactElement } from 'react'

export type PluginSource = 'private-registry' | 'official' | 'local'

export type PluginRiskInfo = {
  id?: string
  permissions: readonly string[]
  source: PluginSource
  lastUpdated: string
}

export type RiskLevel = 'low' | 'medium' | 'high'

export type RiskAssessment = {
  level: RiskLevel
  reasons: string[]
  sensitivePermissions: string[]
}

const SENSITIVE_PERMISSIONS = new Set([
  'audit.write',
  'budget.write',
  'plugin.enable',
  'plugin.disable',
  'member.invite',
  'member.remove',
  'role.assign',
  'session.create',
  'docgraph.submit',
  'kb.bind',
  'organization.delete',
  'ownership.transfer',
])

const RISK_LABELS: Record<RiskLevel, string> = {
  low: '低',
  medium: '中',
  high: '高',
}

const STALE_DAYS = 180

function daysSince(date: string, now: Date): number | null {
  const parsed = Date.parse(`${date}T00:00:00Z`)
  if (Number.isNaN(parsed)) return null
  return Math.floor((now.getTime() - parsed) / 86_400_000)
}

export function assessRisk(info: PluginRiskInfo, now: Date = new Date('2026-09-29T00:00:00Z')): RiskAssessment {
  const sensitive = info.permissions.filter((permission) => SENSITIVE_PERMISSIONS.has(permission))
  const reasons: string[] = []
  let score = 0

  if (sensitive.length >= 3) {
    score += 3
    reasons.push(`敏感权限 ${sensitive.length} 项（${sensitive.join('、')}）`)
  } else if (sensitive.length >= 1) {
    score += 1
    reasons.push(`敏感权限 ${sensitive.length} 项（${sensitive.join('、')}）`)
  } else {
    reasons.push('仅只读类权限')
  }

  if (info.source === 'private-registry') {
    score += 1
    reasons.push('来源为企业私有源，需按企业策略自评')
  } else {
    reasons.push(`来源可信（${info.source}）`)
  }

  const age = daysSince(info.lastUpdated, now)
  if (age === null) {
    score += 1
    reasons.push('缺少可解析的最近更新时间')
  } else if (age > STALE_DAYS) {
    score += 1
    reasons.push(`最近更新距今 ${age} 天（超过 ${STALE_DAYS} 天）`)
  } else {
    reasons.push(`最近更新在 ${STALE_DAYS} 天内`)
  }

  const level: RiskLevel = score >= 3 ? 'high' : score >= 1 ? 'medium' : 'low'
  return { level, reasons, sensitivePermissions: sensitive }
}

export function RiskDisplay({ info }: { info: PluginRiskInfo }): ReactElement {
  const assessment = assessRisk(info)
  return (
    <div className="worknexus-market-risk" data-risk={assessment.level}>
      <p className="worknexus-market-risk-level">风险等级：{RISK_LABELS[assessment.level]}</p>
      <p className="worknexus-market-risk-source">来源：{info.source}</p>
      <p className="worknexus-market-risk-updated">最近更新：{info.lastUpdated}</p>
      <ul className="worknexus-market-risk-permissions">
        {info.permissions.map((permission) => (
          <li key={permission} data-sensitive={String(assessment.sensitivePermissions.includes(permission))}>
            {permission}
          </li>
        ))}
      </ul>
      <ul className="worknexus-market-risk-reasons">
        {assessment.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  )
}
