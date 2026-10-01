/**
 * T-082：样例项目状态视图。
 */

import { describe, expect, it } from 'vitest'
import { renderToString } from 'react-dom/server'

import { ProjectView, SAMPLE_PROJECTS } from '../src/pages/ProjectView.js'
import projects from '../src/data/sample-projects.json'

describe('project view', () => {
  it('renders at least one sample project with its current stage', () => {
    const html = renderToString(<ProjectView projects={projects} />)
    expect(projects.projects.length).toBeGreaterThanOrEqual(1)
    expect(html).toContain(projects.projects[0]!.name)
    expect(html).toContain(projects.projects[0]!.currentStage)
  })

  it('renders the stage list and keeps the demo label', () => {
    const html = renderToString(<ProjectView projects={projects} />)
    expect(html).toContain('示例数据')
    expect(html).toContain(projects.projects[0]!.stages[0]!.name)
    expect(SAMPLE_PROJECTS.demo).toBe(true)
  })
})
