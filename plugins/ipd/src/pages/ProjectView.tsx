/**
 * IPD 样例项目状态视图（T-082，需求书 P5-F04）。
 *
 * 展示样例项目的阶段状态；数据为本地静态示例并显式标注「示例数据」，
 * 不接真实项目管理系统，也不承诺流程自动化。
 */

import type { ReactElement } from 'react'
import sampleProjects from '../data/sample-projects.json'

export type IpdProjectStage = { id: string; name: string; status: string }

export type IpdProject = {
  id: string
  name: string
  owner: string
  currentStage: string
  updatedAt: string
  stages: IpdProjectStage[]
}

export type IpdProjectCollection = {
  demo: boolean
  label: string
  projects: IpdProject[]
}

export const SAMPLE_PROJECTS = sampleProjects as IpdProjectCollection

export function ProjectView(
  { projects = SAMPLE_PROJECTS }: { projects?: IpdProjectCollection },
): ReactElement {
  return (
    <div className="worknexus-ipd-projects" data-demo={String(projects.demo)}>
      <p className="worknexus-ipd-demo-badge">【{projects.label}】样例项目状态</p>
      <ul className="worknexus-ipd-project-list">
        {projects.projects.map((project) => (
          <li key={project.id} data-project={project.id}>
            <div className="worknexus-ipd-project-head">
              <span className="worknexus-ipd-project-name">{project.name}</span>
              <span className="worknexus-ipd-project-stage">当前阶段：{project.currentStage}</span>
              <span className="worknexus-ipd-project-owner">负责人：{project.owner}</span>
            </div>
            <ol className="worknexus-ipd-project-stages">
              {project.stages.map((stage) => (
                <li key={stage.id} data-status={stage.status}>
                  {stage.name}（{stage.status}）
                </li>
              ))}
            </ol>
          </li>
        ))}
      </ul>
    </div>
  )
}
