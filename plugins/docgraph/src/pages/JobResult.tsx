/**
 * DocGraph 结果视图（T-073，需求书 P4-F05）。
 *
 * 规则：
 *  - 结构化结果优先：按 `findings` / `results` 渲染「规则 / 结论 / 严重度 / 说明」表格；
 *  - `result` 三态（pass / fail / unverifiable）**原样保留**，不归一成二态（T-009 §5 约束）；
 *  - 结构未知时回退到原始 JSON（`<pre>`），而不是空白页；
 *  - 「跳转原文」用 `sourceUrl` 或远端返回的链接；不缓存敏感正文到本地未加密存储。
 */

import type { ReactElement } from 'react'

export type DocGraphFinding = {
  rule: string
  message: string
  result: string
  severity: string | null
  source: string | null
}

const RESULT_LABELS: Record<string, string> = {
  pass: '通过',
  fail: '不通过',
  unverifiable: '无法判定',
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

/** 归一化结果条目；缺失字段保留 `null`，不编造（T-009 §5 字段映射约束）。 */
export function normalizeFindings(payload: unknown): DocGraphFinding[] {
  if (typeof payload !== 'object' || payload === null) return []
  const container = payload as Record<string, unknown>
  const raw = Array.isArray(container.findings)
    ? container.findings
    : Array.isArray(container.results)
      ? container.results
      : Array.isArray(payload)
        ? (payload as unknown[])
        : []
  return raw.flatMap((item) => {
    if (typeof item !== 'object' || item === null) return []
    const row = item as Record<string, unknown>
    const rule = asString(row.rule) ?? asString(row.rule_id) ?? asString(row.ruleId)
    const message = asString(row.message) ?? asString(row.detail) ?? asString(row.text)
    if (rule === null && message === null) return []
    return [{
      rule: rule ?? '（未标注规则）',
      message: message ?? '（无说明）',
      result: asString(row.result) ?? 'unknown',
      severity: asString(row.severity),
      source: asString(row.source),
    }]
  })
}

export function findSourceUrl(payload: unknown): string | null {
  if (typeof payload !== 'object' || payload === null) return null
  const container = payload as Record<string, unknown>
  return asString(container.sourceUrl) ?? asString(container.source_url) ?? asString(container.documentUrl)
}

export function JobResult({ result, sourceUrl }: { result: unknown; sourceUrl?: string }): ReactElement {
  const findings = normalizeFindings(result)
  const link = sourceUrl ?? findSourceUrl(result)
  return (
    <div className="worknexus-docgraph-result">
      {findings.length === 0 ? (
        <pre className="worknexus-docgraph-result-raw">{JSON.stringify(result ?? null, null, 2)}</pre>
      ) : (
        <table className="worknexus-docgraph-result-table">
          <thead>
            <tr>
              <th>规则</th>
              <th>结论</th>
              <th>严重度</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((finding, index) => (
              <tr key={`${finding.rule}-${index}`} data-result={finding.result}>
                <td>{finding.rule}</td>
                <td>{RESULT_LABELS[finding.result] ?? finding.result}</td>
                <td>{finding.severity ?? '未知'}</td>
                <td>{finding.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {link === null ? null : (
        <a className="worknexus-docgraph-source-link" href={link} rel="noreferrer" target="_blank">
          {link}
        </a>
      )}
    </div>
  )
}
