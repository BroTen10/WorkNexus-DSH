# 技术决策：知识库 Provider 选型（T-010）

> 任务：T-010 知识库 Provider 选型探针 ｜ 批次 0 ｜ 依赖 T-000 ｜ 无人值守度 C（需外部系统）
> 执行日期：2026-09-28 ｜ 取证方式：上游公开资料只读取证 + 判据分析；**运行期探针未执行**（本机 Docker daemon 未运行）

## 1. 结论先行

1. **首选 RAGFlow，备选 AnythingLLM**（与总览 §2.1 第 5 条默认裁决一致），但**接口按「通用 HTTP RAG Provider」抽象，不与任一实现耦合**。
2. **四项判据的当前判定**：两个候选在「稳定 HTTP API」与「Windows 本机可部署」上均为**成立**；在「空间/文档级权限过滤」上，**RAGFlow 需实测确认**、AnythingLLM 有工作区（workspace）+ 多用户权限的产品形态但**检索侧过滤粒度需实测**；在「可追溯引用」上 RAGFlow 在自述中明确宣称支持可追溯引用，AnythingLLM 未在自述中宣称。
3. **本次未取到运行期证据**：本机 Docker daemon 未运行（`docker ps` 报 `npipe:////./pipe/dockerDesktopLinuxEngine` 不存在），RAGFlow 官方 HTTP API 参考文档页在本次网络下**连接被重置**。因此**所有「检索响应字段」类结论均标「未验证」**，符合总览 §2.1 第 4 条。
4. **对 P3 的落地方式**：先实现 `KnowledgeProvider` 契约 + 通用 `http-rag` Provider（`POST {baseUrl}{searchPath}` 风格，路径可配置），RAGFlow 作为**首个联调对象**，AnythingLLM 作为备选实现；**Provid器接口不因候选变化而改动**。

## 2. 取证来源与命令

| # | 目的 | 命令 / 来源 | 结果 |
| --- | --- | --- | --- |
| 1 | RAGFlow 自述与部署前置 | `curl.exe -sS -L https://raw.githubusercontent.com/infiniflow/ragflow/main/README.md` | 200，17,072 字符 |
| 2 | AnythingLLM 自述 | `curl.exe -sS -L https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md` | 200 |
| 3 | AnythingLLM 开发者 API 文档页 | `https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/docs/API/README.md` | **404** |
| 4 | RAGFlow HTTP API 参考 | `https://raw.githubusercontent.com/infiniflow/ragflow/main/docs/references/http_api_reference.md` | **连接被重置**（未取证） |
| 5 | 本机容器运行时 | `docker ps` | **失败**：daemon 未运行 |
| 6 | 候选检索探针 | 需容器运行 | **未执行** |

RAGFlow README 关键原文摘录（命令 1）：

- `- Intuitive APIs for seamless integration with business.`
- `- Quick view of the key references and traceable citations to support grounded answers.`
- `Docker >= 24.0.0 & Docker Compose >= v2.26.1`
- 镜像 `infiniflow/ragflow:v0.27.2`（README 徽章）
- `2025-12-26 Supports 'Memory' for AI agent.`、`2026-04-24 Supports DeepSeek v4.`、`2026-06-15 Support multiple chat channels…`

AnythingLLM README 关键原文摘录（命令 2）：

- `AnythingLLM supports multiple users as well where you can control the access and experience per user…`
- `👤 Multi-user instance support and permissioning _Docker version only_`
- `📖 Multiple document type support (PDF, TXT, DOCX, etc)`
- `Full Developer API for custom integrations!`
- `Works with all popular closed and open-source LLM providers…`

## 3. 逐项判定表

### 3.1 四项判据逐候选判定

判据（固定，来自 T-010 步骤 1）：① 稳定 HTTP 检索 API；② 空间/文档级权限过滤；③ 可追溯引用（标题/片段/链接）；④ Windows 本机低成本部署。

| 判据 | RAGFlow | 证据强度 | AnythingLLM | 证据强度 |
| --- | --- | --- | --- | --- |
| ① 稳定 HTTP 检索 API | **成立**（自述 "Intuitive APIs for seamless integration with business"；官方有 HTTP API 参考文档，本次未取到正文→**端点路径未验证**） | 自述强、实测缺 | **成立**（自述 "Full Developer API for custom integrations!"；API 文档路径 404→**端点路径未验证**） | 自述强、实测缺 |
| ② 空间/文档级权限过滤 | **待实测**（有数据集/知识库概念，是否支持按空间过滤检索结果未验证） | 弱 | **部分成立**（多用户 + 权限控制为 Docker 版特性；工作区=空间概念；**检索时是否按调用者身份过滤未验证**） | 中 |
| ③ 可追溯引用 | **成立（自述）**：`traceable citations to support grounded answers` | 自述强、字段未验证 | **未宣称**（README 未提引用回溯） | 弱 |
| ④ Windows 本机低成本部署 | **成立**：Docker Compose 单机部署，官方镜像；要求 Docker ≥24 / Compose ≥2.26 | 强 | **成立**：Docker 版为推荐分发形态 | 强 |

RAGFlow 前置版本核对：本机 Docker **29.7.2 ≥ 24.0.0** ✔；Docker Compose **需实测**（本次 daemon 未运行，未取到 `docker compose version`，列为未验证）。

### 3.2 选型结论

| 名次 | 候选 | 理由 | 主要缺口 |
| --- | --- | --- | --- |
| **首选** | **RAGFlow** | 唯一在自述中明确「可追溯引用」，与本需求 §4.3「引用展示」直接对齐；文档解析能力强（RAGFlow 主打深度文档理解），适合企业知识库场景 | 空间级过滤需实测；HTTP API 端点路径未取到 |
| 备选 | **AnythingLLM** | 多用户 + 工作区 + 全量开发者 API，产品形态最贴近「按空间绑定」；部署轻 | 未见引用回溯宣称；权限过滤粒度未验证 |

### 3.3 Provider 抽象（不随候选变化）

> 依据总览 §2.1 第 5 条：**先落地通用 `http-rag` Provider，Provider 接口不变**；第 16 条：**检索只落在企业插件内，不侵入官方会话主链路；检索失败只降级提示**。

```
interface KnowledgeProvider {
  // 元信息：用于健康检查与 UI 展示
  id: string            // 例："http-rag"
  label: string
  // 连接
  healthCheck(): Promise<{ ok: boolean; detail?: string }>
  // 检索：必须显式携带企业侧空间与用户身份，供远端做权限过滤
  search(req: {
    query: string
    spaceIds: string[]        // 企业侧空间绑定（T-063）
    userId: string            // 企业侧用户（用于远端 ACL）
    topK?: number
    filters?: Record<string, unknown>
  }): Promise<KnowledgeHit[]>
}

interface KnowledgeHit {
  docId: string
  title: string
  snippet: string
  score?: number | null      // 远端不给就 null，不编造
  url?: string | null        // 可追溯链接，缺失则 null
  source: string             // provider id
}
```

约束：

1. `score` / `url` 缺失一律 `null`，**禁止本地伪造**（对齐需求书 §6.3 用量与来源口径，以及总览 §2.1 第 15 条精神）。
2. `search` 必须带 `spaceIds` 与 `userId`，**由 Provider 负责透传**，不提供「无身份检索」重载。
3. 检索失败**不得中断会话**，只在企业插件内降级提示（§2.1 第 16 条）。
4. `http-rag` 的 `searchPath` / `healthPath` / 鉴权 header 全部走配置，不做硬编码（为 RAGFlow / AnythingLLM 两条路径留出空间）。

## 4. 裁决记录

| # | 裁决：<决定> — <理由> — <错判代价> |
| --- | --- |
| R-1 | 首选 RAGFlow、备选 AnythingLLM — 总览 §2.1 第 5 条默认裁决，且 RAGFlow 唯一宣称可追溯引用，与 §4.3 引用展示需求对齐 — 若 RAGFlow 的空间级过滤实测不满足，切换到 AnythingLLM 只需新增一个 Provider 实现（接口不变），代价约 0.5 人日 |
| R-2 | 本次以「自述 + 判据分析」出结论，运行期探针登记为未验证 — Docker daemon 未运行、RAGFlow 官方 API 文档页连接被重置，强跑会引入不可信结论 — 若实测推翻首选，T-061~T-066 的 Provider 实现仍是通用 http-rag，返工面被接口隔离住 |
| R-3 | Provider 接口定义**先于**选型结论固化 — §2.1 第 5 条明确「Provider 接口不变」，避免被单一厂商 API 形状绑架 — 若误把厂商字段写进契约，后续换厂商会波及 T-063/T-064 |

## 5. 未验证项与边界

**需真机复核（B 类）**

- B-1：RAGFlow 检索响应体的实际字段（是否含 `document_id` / `title` / `content` / `similarity` / 引用链接），以及是否支持按数据集/空间过滤。缺什么：可用 Docker 环境。怎么补：`docker compose up` 后跑一次最小检索并记录原始 JSON。影响哪条验收：需求书 **§4.3.4 知识库插件六条验收**中「引用可追溯」「空间权限过滤」两条。
- B-2：AnythingLLM 的 workspace 隔离与 API key 权限模型实测。
- B-3：本机 Docker Compose 版本（RAGFlow 要求 ≥ v2.26.1）。

**需外部输入（C 类）**

- C-1：**本机 Docker daemon 不可用**（`docker ps` 失败）。缺什么：可运行的 Docker Desktop / Linux 引擎。怎么补：启动 Docker Desktop 或在具备容器的环境复测。影响哪条验收：P3 全部联调项（§4.3.4）。
- C-2：企业侧知识库空间与文档 ACL 的真实组织方式（来自 P2 的 `spaceIds` 语义），需 T-043/T-046 定稿后回填。

**超出本次范围**

- O-1：不做大规模检索性能与并发压测。
- O-2：不评估复杂 ACL（继承、共享、跨部门授权）——第一版范围见需求书 §4.3.3。
- O-3：不评估更多候选（Dify、FastGPT 等）；如 RAGFlow 与 AnythingLLM 双双不满足，另行立项。

## 6. 对后续任务的约束

1. **T-060**（`KnowledgeProvider` 契约）：直接采用 §3.3 的接口形状；`score`/`url` 可空；`search` 必须带 `spaceIds` 与 `userId`。
2. **T-061**（连接配置与健康检查）：配置项含 `baseUrl`、`searchPath`、`healthPath`、鉴权 header；健康检查失败不阻塞客户端启动。
3. **T-062**（检索与空间权限过滤）：**过滤责任在远端**——Provider 只透传 `spaceIds`；本地不做「取全量再过滤」。
4. **T-063**（空间绑定与会话继承）：企业侧空间 → `spaceIds` 的映射由 Host Core 提供，插件不自行发明空间体系。
5. **T-064**（引用展示与检索日志）：`url` 为空时展示为纯文本引用，不生成假链接。
6. **T-066**（验收门禁与降级验证）：必须包含「Provider 不可达 → 仅降级提示、会话不中断」的断言。
7. **C 类联动**：P3 联调前需人工补齐 C-1（可用 Docker）。在此之前 P3 用契约桩 + 单测推进，不判阻塞。

## 7. 复现命令

```powershell
# 1) 候选自述取证
curl.exe -sS -L "https://raw.githubusercontent.com/infiniflow/ragflow/main/README.md" |
  Select-String -Pattern "Intuitive APIs|traceable citations|Docker >="
curl.exe -sS -L "https://raw.githubusercontent.com/Mintplex-Labs/anything-llm/master/README.md" |
  Select-String -Pattern "Multi-user|Full Developer API"
# 2) 本机容器运行时（当前失败，见 C-1）
docker ps
# 3) 预检查：若 Docker 可用，最小探针（待补）
#   docker compose -f <ragflow>/docker/docker-compose.yml up -d
#   curl.exe -sS -X POST "http://localhost:9380/api/v1/retrieval" -H "Authorization: Bearer <key>" -d "{...}"
```
