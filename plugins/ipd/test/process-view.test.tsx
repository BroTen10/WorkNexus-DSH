/**
 * T-081：样例流程视图——阶段/评审点/交付物/角色 + 示例数据标注。
 */

import { describe, expect, it } from 'vitest'
import { renderToString } from 'react-dom/server'

import { ProcessView, SAMPLE_PROCESS } from '../src/pages/ProcessView.js'
import sample from '../src/data/sample-process.json'

describe('process view', () => {
  it('renders stages, review points, deliverables and roles', () => {
    const stage = sample.stages[0]!
    const html = renderToString(<ProcessView data={sample} />)
    expect(html).toContain(stage.name)
    expect(html).toContain(stage.reviewPoint)
    expect(html).toContain(stage.deliverables[0])
    expect(html).toContain(stage.roles[0])
  })

  it('labels the data as demo and keeps it local/static', () => {
    const html = renderToString(<ProcessView data={sample} />)
    expect(html).toContain('示例数据')
    expect(SAMPLE_PROCESS.demo).toBe(true)
    expect(SAMPLE_PROCESS.stages.length).toBeLessThanOrEqual(5)
    expect(sample.stages.every((stage) => stage.deliverables.length > 0 && stage.roles.length > 0)).toBe(true)
  })
})
