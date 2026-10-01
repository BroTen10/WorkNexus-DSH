/**
 * T-083：P5 验收集成场景（§4.5.4 四条的可执行证据）。
 */

import { describe, expect, it } from 'vitest'
import { renderToString } from 'react-dom/server'

import { IPD_ENTRIES, entriesForActor, visibleEntries } from '../src/index.js'
import { ProcessView } from '../src/pages/ProcessView.js'
import { ProjectView } from '../src/pages/ProjectView.js'
import sampleProcess from '../src/data/sample-process.json'
import sampleProjects from '../src/data/sample-projects.json'
import { renderIpdPrompt } from '../src/prompts.js'

const member = { organizationId: 'o', role: 'member' as const }

describe('P5 acceptance chain', () => {
  it('授权用户可打开 IPD Demo 页面并可看到样例流程与项目状态', () => {
    const entries = entriesForActor(member, 'enterprise')
    expect(entries.map((entry) => entry.id)).toEqual(IPD_ENTRIES.map((entry) => entry.id))

    const processHtml = renderToString(<ProcessView data={sampleProcess} />)
    expect(processHtml).toContain(sampleProcess.stages[0]!.name)
    expect(processHtml).toContain(sampleProcess.stages[0]!.reviewPoint)
    expect(processHtml).toContain(sampleProcess.stages[0]!.deliverables[0])
    expect(processHtml).toContain(sampleProcess.stages[0]!.roles[0])

    const projectHtml = renderToString(<ProjectView projects={sampleProjects} />)
    expect(projectHtml).toContain(sampleProjects.projects[0]!.name)
    expect(projectHtml).toContain(sampleProjects.projects[0]!.currentStage)
  })

  it('未授权成员不可见：个人模式与无组织上下文均为零入口', () => {
    expect(visibleEntries('personal')).toEqual([])
    expect(entriesForActor({ organizationId: '', role: 'viewer' }, 'enterprise')).toEqual([])
    expect(entriesForActor(member, 'personal')).toEqual([])
  })

  it('Demo 插件故障被隔离：渲染异常可捕获且不影响模块其余能力', () => {
    const broken = {
      demo: true,
      label: '示例数据',
      processName: '坏数据',
      stages: null as unknown as typeof sampleProcess.stages,
    }
    expect(() => renderToString(<ProcessView data={broken} />)).toThrow()

    // 故障之后模块其余能力仍可用（无残留全局状态）
    expect(visibleEntries('enterprise')).toHaveLength(3)
    expect(renderToString(<ProjectView projects={sampleProjects} />)).toContain('智能文档平台 V1')
    expect(renderIpdPrompt('ipd-stage-summary', { project: 'P', stage: 'S' }).ok).toBe(true)
  })
})
