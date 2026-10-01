/**
 * IPD 预置 prompt（T-082，需求书 P5-F05）。
 *
 * 只提供「说明 IPD 场景」的模板：变量用 `{{var}}` 占位，缺变量显式报错；
 * 文案不得承诺真实流程自动化（§4.5.3 明确不做流程引擎）。
 */

export type IpdPromptTemplate = {
  id: string
  title: string
  variables: readonly string[]
  template: string
}

export const IPD_PROMPT_TEMPLATES: readonly IpdPromptTemplate[] = Object.freeze([
  {
    id: 'ipd-stage-summary',
    title: '总结当前阶段',
    variables: ['project', 'stage'],
    template:
      '这是 IPD Demo 的示例场景。请基于样例项目「{{project}}」在 {{stage}} 的状态，'
      + '总结该阶段的评审点、应交付物与当前风险；只使用我提供的信息，不要编造。',
  },
  {
    id: 'ipd-review-prep',
    title: '准备评审材料',
    variables: ['project', 'reviewPoint'],
    template:
      '这是 IPD Demo 的示例场景。请为样例项目「{{project}}」的 {{reviewPoint}} 起草评审材料清单，'
      + '并标明每项材料由哪个角色负责。',
  },
])

export type RenderPromptResult =
  | { ok: true; text: string }
  | { ok: false; reason: 'unknown-template' | 'missing-variable'; detail: string }

const PLACEHOLDER = /\{\{([a-zA-Z0-9_]+)\}\}/g

export function renderIpdPrompt(
  templateId: string,
  variables: Record<string, string>,
): RenderPromptResult {
  const template = IPD_PROMPT_TEMPLATES.find((item) => item.id === templateId)
  if (template === undefined) {
    return { ok: false, reason: 'unknown-template', detail: `未知模板: ${templateId}` }
  }
  const missing = template.variables.filter((name) => {
    const value = variables[name]
    return typeof value !== 'string' || value.length === 0
  })
  if (missing.length > 0) {
    return { ok: false, reason: 'missing-variable', detail: `缺少变量: ${missing.join(', ')}` }
  }
  return { ok: true, text: template.template.replace(PLACEHOLDER, (_match, name: string) => variables[name] ?? '') }
}
