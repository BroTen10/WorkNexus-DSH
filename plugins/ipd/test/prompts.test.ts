/**
 * T-082：预置 prompt 的变量渲染与「不承诺自动化」边界。
 */

import { describe, expect, it } from 'vitest'

import { IPD_PROMPT_TEMPLATES, renderIpdPrompt } from '../src/prompts.js'

describe('ipd preset prompts', () => {
  it('renders a template with its variables', () => {
    const result = renderIpdPrompt('ipd-stage-summary', { project: '智能文档平台 V1', stage: '计划阶段' })
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.text).toContain('智能文档平台 V1')
      expect(result.text).toContain('计划阶段')
      expect(result.text).not.toContain('{{')
      expect(result.text).toContain('示例场景')
    }
  })

  it('reports missing variables and unknown templates explicitly', () => {
    expect(renderIpdPrompt('ipd-stage-summary', { project: 'A' })).toMatchObject({
      ok: false,
      reason: 'missing-variable',
    })
    expect(renderIpdPrompt('nope', {})).toMatchObject({ ok: false, reason: 'unknown-template' })
  })

  it('never claims real process automation', () => {
    const text = IPD_PROMPT_TEMPLATES.map((template) => template.template).join('\n')
    expect(text).not.toContain('自动执行')
    expect(text).not.toContain('自动审批')
    expect(text).toContain('不要编造')
  })
})
