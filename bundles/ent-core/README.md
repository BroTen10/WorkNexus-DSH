# @worknexus/ent-core —— WorkNexus-DSH 企业基座 bundle

> P1 交付物之一：Host Core 随发行版**预置**在 profile 的 bundle 段，普通用户不能靠卸载插件移除它。
> 相关任务：T-023（本 bundle + 失败隔离）、T-029（契约骨架接入）、T-035（运行模式门控）。

## 1. 它是什么

一个**第一方 bundle 包**，通过 `package.json` 的 `dsh.bundle.patch` 声明自己是一个 profile bundle layer。
发行版把它的路径写进 `$DSH_HOME/profiles/desktop/package.json` 的 `dsh.profile.bundles` 数组，
位置**在官方 bundle 之后**：

```json
"dsh": {
  "profile": {
    "bundles": [
      "@deepseek-ai/dsh-base",
      "@deepseek-ai/dsh-web-app",
      "@worknexus/ent-core"
    ]
  }
}
```

装配后的 profile 树会多出一个 `# == @worknexus/ent-core` bundle 段（T-005 实测形态）。

## 2. 硬约束（来自 T-005 实测，改本包前必读）

| # | 约束 | 违反后果 |
| --- | --- | --- |
| C-1 | 必须声明 `dsh.bundle.patch` | 被 `skipping profile bundle … declares no dsh.bundle` 跳过，企业基座**静默不存在** |
| C-2 | patch 必须用 `- insert:` 新增行 | 写成 `- id: <新 id>` 会报 `patch: entry "<id>" not found` |
| C-3 | 不得删除或重排官方 bundle 行 | 命中 T-002 §4 N-3（改插件加载行为），且上游升级冲突 |
| C-4 | 不得改官方 `main.ts` / preload / IPC | 命中 T-002 §4 N-6（改安全基线） |
| C-5 | 不得把企业数据/控制面依赖放进本包 | 违反需求书 §4.1.4 第 2 条与 T-029 禁止事项 |

## 3. 失败隔离

两条独立的隔离路径，均由 `scripts/verify_t023_bundle.py` 断言：

1. **解析失败隔离**：把一行指向不存在的模块时，`dsh` 只打印 warning，其余 bundle 段照常装配，退出码仍为 0。
2. **启动失败隔离**：`./failing` 是故意抛错的插件模块，**不随发行版启用**；门禁在一个隔离的故障 profile 中启用它，
   并断言官方 bundle 段与 `ent-core` 健康探针段**仍然存在**。

> 说明：本门禁的证据是**装配层（composition）**的隔离性。真正的 Boot 层隔离（进程内插件 apply 抛错后的存活）
> 需要真机 Electron 运行，登记为 B 类待人工复核——见 `docs/企业bundle预置_T-023.md` §4。

## 4. `protected` 的真相

`package.json` 里的 `dsh.protected` / `dsh.hostInfrastructure` 目前是**声明性标注**：
T-005 实测**未观察到** Loader 级强制力，且实测**用户层 patch 可以把本 bundle 的条目置为 disabled**。

因此本包配套的「不可拆卸」保障是**行为性**的，而不是靠标记：

- profile 的 `dsh.profile.bundles` 属 profile 层，用户层无法摘除（T-005 P-3 实测）；
- 被禁用时的**一次性恢复入口**与**企业数据不丢**由 T-023 的恢复路径负责（见下节）。

## 5. 恢复入口

`scripts/verify_t023_bundle.py --restore <DSH_HOME>` 会把一个 profile 的
`dsh.profile.bundles` 修复为「官方 bundle 在前、`@worknexus/ent-core` 在后」的形态，
并**只重写 bundle 清单**——不动会话、不动设置、不动凭据、不动工作区，因此企业数据不丢。

该入口在 P1 以脚本形式交付；P2 起由企业管理插件以 UI 形式提供（T-050）。

## 6. 文件

| 文件 | 作用 |
| --- | --- |
| `package.json` | bundle 声明（`dsh.bundle.patch`、兼容区间、`protected` 标注） |
| `cordis.patch.yml` | 两行 `insert`：契约骨架挂载点 + 健康探针 |
| `index.js` | 健康探针插件（零副作用） |
| `skeleton.js` | 契约骨架挂载点（T-029 接入 `packages/contracts`） |
| `failing.js` | 故意失败的插件，**仅**供失败隔离门禁使用 |
