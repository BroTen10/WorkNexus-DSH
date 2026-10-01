/**
 * T-073：结果视图——结构化 findings、原文跳转与原始 JSON 兜底。
 */

import { describe, expect, it } from 'vitest'
import { renderToString } from 'react-dom/server'

import { JobResult, findSourceUrl, normalizeFindings } from '../src/pages/JobResult.js'

describe('job result', () => {
  it('renders structured findings and a source link', () => {
    const html = renderToString(
      <JobResult result={{ findings: [{ rule: 'R1', message: '缺少签章', result: 'fail', severity: 'high' }], sourceUrl: 'https://d/1' }} />,
    )
    expect(html).toContain('缺少签章')
    expect(html).toContain('https://d/1')
    expect(html).toContain('R1')
    expect(html).toContain('不通过')
    expect(html).toContain('high')
  })

  it('keeps the three-state result untouched and marks missing fields explicitly', () => {
    const findings = normalizeFindings({
      results: [
        { rule: 'R1', detail: 'a', result: 'pass' },
        { rule: 'R2', detail: 'b', result: 'fail' },
        { rule: 'R3', detail: 'c', result: 'unverifiable' },
      ],
    })
    expect(findings.map((finding) => finding.result)).toEqual(['pass', 'fail', 'unverifiable'])
    expect(findings[0]?.severity).toBeNull()
    expect(findings[0]?.source).toBeNull()

    const html = renderToString(<JobResult result={{ results: [{ rule: 'R3', detail: 'c', result: 'unverifiable' }] }} />)
    expect(html).toContain('无法判定')
    expect(html).toContain('未知')
  })

  it('falls back to raw JSON when the structure is unknown', () => {
    const html = renderToString(<JobResult result={{ weird: { nested: true } }} />)
    expect(html).toContain('weird')
    expect(html).toContain('nested')
    expect(normalizeFindings({ weird: { nested: true } })).toEqual([])
    expect(findSourceUrl({ source_url: 'https://d/2' })).toBe('https://d/2')
  })
})
