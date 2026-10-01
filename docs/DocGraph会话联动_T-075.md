# DocGraph Agent 会话联动（T-075）

## 1. 结论先行

1. `plugins/docgraph/src/agent-bridge.ts` 交付 `buildResultReference()`：产出 `{ type: 'docgraph.result', jobId, spaceId, summary, text }` 的可引用对象，文本含任务号、结果摘要、发现数量与原文链接（P4-F09）。
2. 引用**必须带空间上下文**：`referenceIsVisible()` / `decideReference()` 按会话空间（项目空间 / 部门 / 组织）校验，越权结果返回 `{ ok: false, reason: 'denied' }`，不得进入会话。
3. `buildReferencePrompt()` 生成预置 prompt，明确「这是 DocGraph 结果引用」并禁止编造引用之外的内容；不承诺任何自动化。
4. 官方未提供的能力（`session.delete` / `session.fork` / `transcript.replay` / `transcript.export`）通过 `requestUnsupportedCapability()` **显式返回不支持**，并给出「复制结果摘要到会话」的降级路径（§2.1 第 14 条）。
5. 不接管交互主链路：模块只做纯函数构造，不实现 `AgentTransport`、不调用会话执行接口、不新增 IPC。
6. 裁决：会话可视范围与 T-062 的检索过滤口径保持一致（项目空间/部门/组织三级）— 理由是同一会话的可见性规则不应出现两套 — 错判代价：若将来收紧为「仅项目空间」，需同时改 T-062 与本模块。
7. 裁决：不支持能力统一返回文本说明而非抛错 — 理由是调用方（会话 UI）需要展示而非崩溃 — 错判代价：调用方必须显式判断 `unsupported` 字段，否则可能只显示通用错误。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `plugins/docgraph/src/agent-bridge.ts` | 新增 | 引用构造、空间校验、预置 prompt、不支持能力显式返回 |
| `plugins/docgraph/test/agent-bridge.test.ts` | 新增 | 4 用例：引用构造、链接与发现数、跨空间拒绝、不支持能力 |
| `plugins/docgraph/src/index.ts` | 修改 | 导出会话联动模块 |
| `scripts/verify_t075_docgraph_agent.py` | 新增 | 单任务门禁 |
| `docs/DocGraph会话联动_T-075.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件，差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | 插件测试 | `vitest run` = **20 passed**（agent-bridge 4） | 通过 |
| V-2 | 类型检查 | `tsc -p tsconfig.json --noEmit` exit 0 | 通过 |
| V-3 | 单任务门禁 | `python scripts/verify_t075_docgraph_agent.py` = **6 [OK] / 0 [FAIL]** | 通过 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真实会话内「回答 + DocGraph 引用」的展示与交互。
- B-2：官方会话对引用文本的呈现方式（是否需要额外槽位或消息结构）。

**需外部输入（C 类）**

- C-1：DocGraph 现网结果样本与真实文档链接。

**超出本次范围**

- O-1：不实现 `AgentTransport`、不接管会话执行、不做转录回放/Fork/删除会话（§11）。
- O-2：不做自动化编排（后台自动化属 P6A）。

## 5. 复现命令

```powershell
cd "<repo-root>"
pnpm --filter @worknexus/plugin-docgraph test
python scripts/verify_t075_docgraph_agent.py
```

## 6. 下一步

1. T-076：P4 收尾门禁 —— 逐条核对 §4.4.4 五条、DocGraph 中断隔离、§11 负向清单。
