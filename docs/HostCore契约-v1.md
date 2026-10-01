# Host Core 契约 v1（冻结）

> **冻结版本**：`HOST_CORE_CONTRACT_VERSION = '1.1.0'`（八类契约于 2026-09-29 以 `1.0.0` 初始冻结；`1.1.0` 为 T-060 的次版本递增）；**冻结日期**：2026-09-29；**上游基线**：`dsh-v0.2.0-rc.2`（契约初始冻结时的基线为 `dsh-v0.2.0-rc.1`，2026-09-29 随基线迁移更新，见 `内部基线迁移记录`）。
> **最高边界**：企业侧只扩展官方 DSH Desktop，不替代客户端壳、会话执行、插件装载、更新算法、凭据存储和事件机制。

## 1. 契约定位

Host Core 契约是企业插件、企业控制面和 P3~P6 业务插件之间的**最小可判定语义面**，不是新的运行时内核。契约包 `@worknexus/contracts` 只提供类型、常量和零依赖纯函数；运行期实现分别落在官方机制或 `@worknexus/host-core`、`@worknexus/plugin-runtime` 的薄适配层。

八类契约与需求书 §3.2 一一对应；契约⑨ `KnowledgeProvider` 是 P3 阶段的**扩展契约**（T-060），与八类同包发布，但不改变上述八类的语义与归属：

| # | 契约 | 归属 | 保护标记 | 插件可见性 |
| --- | --- | --- | --- | --- |
| ① | `IdentityContext` | 企业侧登录态投影 | `ent` 前缀 | 只读 |
| ② | `SpaceContext` | 企业空间上下文 | 企业侧 | 只读 |
| ③ | `PermissionPolicy` | 企业服务端最终裁决 | 企业侧 | 只读预判 |
| ④ | `AuditSink` | 企业审计接收面 | 企业侧 | 只写 |
| ⑤ | `UsageLedger` | 企业用量账本 | 企业侧 | 只追加 |
| ⑥ | `EventBus` | 官方事件机制 + 企业命名空间 | 官方承载 | 白名单订阅 |
| ⑦ | `PluginGovernanceView` | 官方 plugin-manager 状态只读镜像 | 官方权威 | 只读 |
| ⑧ | `UpdateManager` | 官方更新 + 上游跟随策略 | 官方权威 | 只读契约 |
| ⑨ | `KnowledgeProvider` | 知识库检索能力面（P3 扩展） | 企业侧 | 只读契约 |

企业字段统一使用 `ENTERPRISE_FIELD_PREFIX = 'ent'` 命名空间，不覆盖官方 `identity`、`credentials`、`api` 语义。

## 2. 契约签名与语义

### ① `IdentityContext`

```ts
type RunMode = 'personal' | 'enterprise'

type IdentityContext = {
  userId: string
  email: string
  organizationIds: string[]
  sessionTokenExpiresAt: string
  mode: RunMode
}

const PERSONAL_IDENTITY: Readonly<IdentityContext>
const IDENTITY_FIELD_PREFIX: 'ent'
```

语义：

1. 该契约只描述当前登录态和组织归属；凭据、Token、密码和 API Key 不进入契约。
2. `mode` 是运行模式投影，最终由 T-035 的 `ModeProvider` 判定；本契约不提供手工模式开关。
3. `PERSONAL_IDENTITY` 是无登录、无组织的默认个人模式形态。
4. 官方客户端不需要理解本契约；企业字段在插件载荷中必须用 `ent` 前缀。

### ② `SpaceContext`

```ts
type Role = 'owner' | 'admin' | 'member' | 'viewer'
const ROLES: readonly ['owner', 'admin', 'member', 'viewer']
const ROLE_RANK: Readonly<Record<Role, number>>

type SpaceContext = {
  organizationId: string
  departmentId?: string
  projectSpaceId?: string
  role: Role
}

function hasAtLeastRole(actor: SpaceContext, minimum: Role): boolean
```

语义：

1. 四类角色固定为 `owner > admin > member > viewer`。
2. `hasAtLeastRole()` 是纯函数预判；企业服务端的权限裁决仍归 `PermissionPolicy`。
3. 空间层级字段可省略；未提供部门或项目空间时语义是组织级上下文，不能臆造默认空间。

### ③ `PermissionPolicy`

```ts
type Action =
  | 'space.read' | 'space.write'
  | 'member.invite' | 'member.remove' | 'role.assign'
  | 'plugin.enable' | 'plugin.disable'
  | 'audit.read' | 'usage.read' | 'budget.write'
  | 'kb.retrieve' | 'kb.bind'
  | 'docgraph.submit' | 'docgraph.read'
  | 'session.create'

const ACTIONS: readonly Action[]

type ResourceRef = { type: string; id: string }

interface PermissionPolicy {
  can(actor: SpaceContext, action: Action, resource: ResourceRef): boolean
}

const DENY_ALL_POLICY: PermissionPolicy
const READ_ONLY_FOR_VIEWER_POLICY: PermissionPolicy
```

语义：

1. `Action` 是固定枚举；企业插件声明必须引用 `ACTIONS`，不得自定义权限点。
2. 默认拒绝：`DENY_ALL_POLICY` 对所有动作返回 false。
3. `READ_ONLY_FOR_VIEWER_POLICY` 只是 P1/P2 本地预判基线；企业服务端策略是最终权威。
4. 客户端 `can()` 结果不得用于绕过服务端校验。

### ④ `AuditSink`

```ts
type AuditResult = 'success' | 'failure' | 'denied'

type AuditEvent = {
  eventId: string
  timestamp: string
  userId: string
  organizationId: string
  spaceId?: string | null
  action: string
  resourceType: string
  resourceId?: string | null
  result: AuditResult
  device: string
  summary: string
}

interface AuditSink {
  write(event: Omit<AuditEvent, 'eventId' | 'timestamp'>): Promise<void>
}

const AUDIT_SUMMARY_MAX_LENGTH = 200
function summarize(text: string): string
```

语义：

1. 审计只追加。契约面没有 `update`、`delete` 或 `read`。
2. 纠正历史事实必须追加更正事件；后续控制面实现必须携带 `corrects_event_id` 类字段，不得原地改写。
3. `summary` 必须经 `summarize()` 截断；不得记录完整 prompt、完整模型输出、密码、验证码或 API Key。
4. `eventId` 和 `timestamp` 由 Sink 生成，调用方不得伪造。

### ⑤ `UsageLedger`

```ts
type UsageRecordSource = 'dsh_event' | 'adapter_estimate' | 'manual_import'
const USAGE_SOURCES: readonly UsageRecordSource[]

type UsageRecord = {
  usageId: string
  timestamp: string
  organizationId: string
  spaceId: string | null
  userId: string
  sessionId: string | null
  pluginId: string | null
  provider: string
  model: string
  promptTokens: number | null
  completionTokens: number | null
  totalTokens: number | null
  estimatedCost: number | null
  source: UsageRecordSource
}

interface UsageLedger {
  record(entry: Omit<UsageRecord, 'usageId' | 'timestamp'>): Promise<void>
  query(q: { organizationId: string; spaceId?: string; from: string; to: string }): Promise<UsageRecord[]>
}

function deriveTotalTokens(promptTokens: number | null, completionTokens: number | null): number | null
```

语义：

1. 用量记录只追加；没有更新和删除路径。
2. `source` 固定三值。无法从官方 session、账号用量或 telemetry 获得的字段必须留 `null`，不得推算。
3. `deriveTotalTokens()` 只有在 prompt 与 completion 都非 null 时才求和；任一为 null 就返回 null。
4. `adapter_estimate` 必须来自真实投影；禁止为了报表完整而生成凭空数字。

### ⑥ `EventBus`

```ts
const ENTERPRISE_EVENT_NAMESPACE = 'ent'
const ENTERPRISE_EVENT_TOPICS: readonly EnterpriseEventTopic[]

type EnterpriseEventTopic =
  | 'ent.identity.changed'
  | 'ent.space.switched'
  | 'ent.audit.written'
  | 'ent.usage.recorded'
  | 'ent.plugin.state.changed'
  | 'ent.update.availability.changed'

type EnterpriseEvent = {
  topic: EnterpriseEventTopic
  occurredAt: string
  actorUserId: string
  organizationId: string
  spaceId?: string | null
  payload: Readonly<Record<string, unknown>>
  source: string
}

type Unsubscribe = () => void

interface EventBus {
  publish(event: EnterpriseEvent): Promise<void>
  subscribe(topic: EnterpriseEventTopic, handler: (event: EnterpriseEvent) => void): Unsubscribe
  allowedTopics(): readonly EnterpriseEventTopic[]
}

function isEnterpriseTopic(value: string): value is EnterpriseEventTopic
function assertEnterpriseTopic(topic: string): EnterpriseEventTopic
```

运行期薄适配层签名：

```ts
interface OfficialEventContext {
  emit(topic: string, event: EnterpriseEvent): void
  on(topic: string, handler: (event: EnterpriseEvent) => void): void | (() => void)
}

type EnterpriseEventChannel = {
  publish(event: EnterpriseEvent): void
  subscribe(topic: string, handler: (event: EnterpriseEvent) => void): () => void
  allowedTopics(): readonly EnterpriseEventTopic[]
}

function createEnterpriseEventChannel(deps: {
  official: OfficialEventContext
  onError?: (input: { topic: EnterpriseEventTopic; event: EnterpriseEvent; error: unknown }) => void
}): EnterpriseEventChannel
```

语义：

1. 事件承载权属于官方 Cordis `Context`；适配层调用官方 `emit()` / `on()`，不保存事件、不排队、不维护第二套总线。
2. 企业 topic 只能是 `ent.*` 白名单；白名单外不注册、不发布。
3. 一个订阅者抛错必须通过 `onError` 上报，不得影响其他订阅者和官方分发。
4. `source` 用于区分事件来源，禁止用来源字段伪造审计主体。

### ⑦ `PluginGovernanceView`

```ts
type PluginHealth = { ok: boolean; detail?: string }
type PluginState = 'installed' | 'enabled' | 'disabled' | 'failed'

type PluginView = {
  id: string
  version: string
  enabled: boolean
  protected: boolean
  health: PluginHealth
}

interface PluginGovernanceView {
  list(): Promise<PluginView[]>
  stateOf(pluginId: string): Promise<PluginState>
  isAllowed(pluginId: string, version: string): boolean
}

const PERSONAL_MODE_GOVERNANCE: PluginGovernanceView
```

治理挂接签名：

```ts
type GovernancePluginRef = { pluginId: string; version: string }
type GovernanceAuditEntry = {
  action: 'plugin.install' | 'plugin.enable' | 'plugin.disable' | 'plugin.uninstall' | 'plugin.changed'
  pluginId: string
  version: string
  result: 'success' | 'failure' | 'denied'
  detail?: string
  source: 'official-plugin-manager'
}

function createGovernanceHooks(deps: {
  whitelist: readonly string[]
  audit: (entry: GovernanceAuditEntry) => Promise<void> | void
}): {
  onInstall(event: GovernancePluginRef): Promise<{ decision: 'allow' | 'deny'; reason?: string }>
  onEnable(event: GovernancePluginRef): Promise<void>
  onDisable(event: GovernancePluginRef): Promise<void>
  onUninstall(event: GovernancePluginRef): Promise<void>
  onPluginOrBundleChanged(event: { reason: 'plugin' | 'bundle' }): Promise<void>
}

function attachGovernanceHooks(deps: {
  official: {
    on(topic: 'plugin-manager/changed', handler: (event: { reason: 'plugin' | 'bundle' | 'install' | 'remove' }) => void): void | (() => void)
  }
  hooks: ReturnType<typeof createGovernanceHooks>
  onError?: (error: unknown) => void
}): () => void
```

语义：

1. 官方 plugin-manager 是安装、启用、禁用、卸载、升级、回滚、健康检查和失败上报的唯一权威。
2. 契约面不提供 `enable()` / `disable()`；企业侧只做白名单、审批状态和审计。
3. 上游 `plugin-manager/changed` 只携带 `reason`，不携带插件 id/version；`install`、`remove` 可映射，`plugin` / `bundle` 记录为 `plugin.changed`，不得臆造启停方向。
4. 治理钩子异常必须隔离。安装钩子失败返回 `deny`；启停、卸载和 changed 审计失败不得阻塞官方操作。
5. `protected: true` 是企业侧标注，不能替代官方保护机制的实际行为。

### ⑧ `UpdateManager`

```ts
type UpdateChannel = 'stable' | 'canary'

type UpdateCheckInput = {
  currentVersion: string
  channel: UpdateChannel
  mandatory: boolean
}

type UpdateCheckResult = {
  available: boolean
  currentVersion: string
  targetVersion: string | null
  mandatory: boolean
  channel: UpdateChannel
}

type UpdateOperationResult = { ok: boolean; detail?: string }
type UpdateRollbackResult = { ok: boolean; restoredVersion: string; detail?: string }

type UpstreamPin = {
  tag: string
  commit: string
  diffsetPatch: string | null
  rebaseDrillRecord: string | null
}

interface UpdateManager {
  check(input: UpdateCheckInput): Promise<UpdateCheckResult>
  download(input: { targetVersion: string }): Promise<UpdateOperationResult>
  install(input: { targetVersion: string }): Promise<UpdateOperationResult>
  rollback(input: { organizationId: string }): Promise<UpdateRollbackResult>
  upstreamPin(): Promise<UpstreamPin>
}
```

语义：

1. 更新算法、下载校验、安装交接、降级禁止和签名流程由官方实现。
2. 企业契约只补充上游跟随策略：锁定 tag、commit、差异集补丁和 rebase 演练记录。
3. `rollback()` 必须能回到「最近可用」版本，`restoredVersion` 不一定是最新版本。
4. 禁止在企业侧定义第二套更新源、更新算法或凭据存储。

### ⑨ `KnowledgeProvider`（P3 扩展，T-060）

```ts
type KnowledgeHealth = 'healthy' | 'unreachable' | 'auth_failed' | 'sync_failed'

type KnowledgeChunk = {
  documentId: string
  title: string
  snippet: string
  url?: string
  score: number
  spaceId?: string
}

type KnowledgeConfigValidation = { ok: boolean; problems: string[] }
type KnowledgeHealthReport = { state: KnowledgeHealth; detail?: string }
type KnowledgeRetrieveInput = { query: string; spaceContext: SpaceContext; limit: number }

interface KnowledgeProvider {
  readonly id: string
  healthCheck(): Promise<KnowledgeHealthReport>
  validateConfig(config: unknown): KnowledgeConfigValidation
  retrieve(input: KnowledgeRetrieveInput): Promise<KnowledgeChunk[]>
}
```

语义：

1. 四项能力与需求书 §4.3.2 P3-F01 一一对应：检索（`retrieve`）、健康检查（`healthCheck`）、配置校验（`validateConfig`）、权限过滤（`retrieve` 必须接收 `spaceContext`）。
2. 契约只定义能力面，**不写具体 Provider 实现细节**（RAGFlow / AnythingLLM / http-rag 均是可替换实现）；Provider 的构造参数、鉴权方式和端点路径不属于契约。
3. 权限过滤是双层职责：调用方先做 `PermissionPolicy.can(actor, 'kb.retrieve', ...)` 判定，Provider 侧按 `spaceContext` 丢弃不属于该空间的命中；无权限时**不得调用 Provider**。
4. 状态四态互斥（P3-F07）：`healthy` / `unreachable` / `auth_failed` / `sync_failed`；`detail` 只放可公开摘要，不得含 Token 或正文。
5. 检索失败一律降级为「无命中 + 提示」，不向官方会话主链路抛未捕获异常（需求书 §5.4 第 3 条、总览 §2.1 第 16 条）。

## 3. 版本策略与迁移规则

1. 契约版本当前为 `1.1.0`，由 `packages/contracts/src/version.ts` 唯一声明；`1.0.0` 的八类契约语义未变更。
2. 本仓库采用总览 §2.1 第 17 条的内部策略：**破坏性变更 → minor 递增；新增字段 → patch 递增**。
3. 任何变更必须在本文档「变更留痕」登记：变更类型、影响契约、旧/新签名、消费者迁移、版本号和评审人。
4. 新增字段必须是可选字段；删除字段、收窄类型、改变默认值、改变错误语义都按破坏性处理。
5. 企业插件声明的 `hostCoreCompatibility` 使用 semver range；不满足契约版本时拒绝，不降级为警告。
6. 官方 plugin-manager 实际使用 `peerDependencies` 做 DSH 版本预检；`dshCompatibility` 是企业侧复核字段，两者都要满足，但企业实现不得替代官方安装预检。
7. 冻结后不允许无留痕修改。若需求与官方实现冲突，先修改需求登记 §13.3，再进入契约变更评审。

## 4. 冻结评审矩阵

| # | 评审项 | 结论 | 证据 |
| --- | --- | --- | --- |
| 1 | 八类契约逐条存在 | 通过 | `packages/contracts/src/{identity,space,permission,audit,usage,event,plugin,update}.ts` |
| 2 | 契约版本可导入且为 `1.0.0` | 通过 | `HOST_CORE_CONTRACT_VERSION` 与 T-029 门禁 |
| 3 | 命名不覆盖官方 `identity/credentials/api` | 通过 | `ENTERPRISE_FIELD_PREFIX='ent'` |
| 4 | 插件治理只读，无启停语义 | 通过 | `PluginGovernanceView` 无 `enable/disable`；负向测试断言 |
| 5 | 更新契约收窄为跟随策略 | 通过 | `upstreamPin()` + 官方四方法面，无更新算法 |
| 6 | 事件复用官方机制并命名空间隔离 | 通过 | `createEnterpriseEventChannel()` 只调用官方 `emit()/on()` |
| 7 | 审计与用量只追加、缺失不猜 | 通过 | Sink 无 update/delete；Usage 无 update/delete；null 语义测试 |
| 8 | 企业声明与官方 bundle 声明不冲突 | 通过 | T-031 官方字段透传与企业字段共存测试 |
| 9 | 契约⑨ 覆盖 P3-F01 四项能力且不绑实现 | 通过 | `packages/contracts/src/knowledge.ts` + `test/knowledge.test.ts`（T-060） |

## 5. 消费者对接点

| 消费者 | 必须消费的契约 | 对接要求 |
| --- | --- | --- |
| T-035 | `IdentityContext`、`SpaceContext` | 由登录态和组织上下文推导 `RunMode`，不提供手工开关 |
| T-041 | `AuditSink`、`UsageLedger`、`PluginInstall` | 只追加建模；插件安装权威来自官方 plugin-manager |
| T-060 | `SpaceContext`、`PermissionPolicy`、`UsageLedger` | 知识库检索必须过滤权限并记录真实用量 |
| T-090 | `EventBus`、`UpdateManager` | 只薄适配官方 ACP 与更新策略，不接管会话 |
| T-100 | `PluginGovernanceView`、`UpdateManager` | 官方市场/插件状态只读嵌入，不重写生命周期 |

## 6. 变更留痕

| 版本 | 日期 | 变更 | 消费者迁移 | 评审 |
| --- | --- | --- | --- | --- |
| `1.0.0` | 2026-09-29 | 初始冻结：八类契约、`ent` 命名空间、只读治理视图、上游跟随策略、官方事件薄适配层 | 首版，无迁移 | T-034 冻结评审 |
| `1.1.0` | 2026-09-29 | 次版本递增：新增契约⑨ `KnowledgeProvider`（检索/健康检查/配置校验/权限过滤）；八类契约语义零变更 | 纯新增，消费者无需迁移；`hostCoreCompatibility: ">=1.0.0"` 的既有插件继续有效 | T-060 交付评审 |

## 7. 交付说明

### 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `docs/HostCore契约-v1.md` | 修改 | T-030 草稿升级为 v1 定稿 |
| `scripts/verify_t034_contract_doc.py` | 新增 | 契约文档冻结一致性门禁 |

### 验证证据表

| # | 命令 | 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | `pnpm --filter @worknexus/contracts test` | `Tests 13 passed (13)` | 通过 |
| V-2 | `pnpm --filter @worknexus/plugin-runtime test` | `Tests 15 passed (15)` | 通过 |
| V-3 | `pnpm --filter @worknexus/host-core test` | `Tests 4 passed (4)` | 通过 |
| V-4 | `python scripts/verify_t034_contract_doc.py` | `7 [OK] / 0 [FAIL]` | 通过 |

### 未验证项与边界

**需真机复核（B 类）**

- B-1：真实 Cordis Context、官方 plugin-manager 与更新器的运行期装配仍按 T-032/T-033/T-030 的 B 类项复核。

**需外部输入（C 类）**

- C-1：企业 bundle 最终命名、私有源地址和正式更新源仍是外部输入。

**超出本次范围**

- O-1：不实现控制面业务接口、AgentTransport、第二套插件生命周期、第二套事件总线或更新算法。

### 复现命令

```powershell
cd "<repo-root>"
pnpm install
pnpm --filter @worknexus/contracts test
pnpm --filter @worknexus/plugin-runtime test
pnpm --filter @worknexus/host-core test
python scripts/verify_t034_contract_doc.py
```

### 下一步

1. 执行 T-035，把 `IdentityContext` 和 `SpaceContext` 转为 `ModeContext` 门控。
2. T-041 起按只追加语义建模审计、用量和插件安装记录。
3. 任何契约变化先递增版本、更新本文档变更留痕，再改实现。
