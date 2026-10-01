/**
 * IPD 样例流程视图（T-081，需求书 P5-F02 / P5-F03）。
 *
 * 展示样例阶段、评审点、交付物与角色；数据是**少量本地静态示例**，
 * 页面顶部显式标注「示例数据」，不接真实业务数据源、不做流程引擎。
 */

import type { ReactElement } from 'react'
import sampleProcess from '../data/sample-process.json'

export type IpdStage = {
  id: string
  name: string
  reviewPoint: string
  deliverables: string[]
  roles: string[]
}

export type IpdProcess = {
  demo: boolean
  label: string
  processName: string
  stages: IpdStage[]
}

export const SAMPLE_PROCESS = sampleProcess as IpdProcess

export function ProcessView({ data = SAMPLE_PROCESS }: { data?: IpdProcess }): ReactElement {
  return (
    <div className="worknexus-ipd-process" data-demo={String(data.demo)}>
      <p className="worknexus-ipd-demo-badge">【{data.label}】{data.processName}</p>
      <table className="worknexus-ipd-process-table">
        <thead>
          <tr>
            <th>阶段</th>
            <th>评审点</th>
            <th>交付物</th>
            <th>角色</th>
          </tr>
        </thead>
        <tbody>
          {data.stages.map((stage) => (
            <tr key={stage.id} data-stage={stage.id}>
              <td>{stage.name}</td>
              <td>{stage.reviewPoint}</td>
              <td>{stage.deliverables.join('、')}</td>
              <td>{stage.roles.join('、')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
