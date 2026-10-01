# P5 IPD Demo 插件收尾（T-083）

## 1. 结论先行

1. 批次 6（T-080~T-083）已全部实现并提交；`verify_t083_p5.py` 汇总 3 个子门禁、Python/TypeScript 全量回归、验收与范围核查，结果 **10 [OK] / 0 [FAIL]**。
2. 交付面：官方 UI 插件形态与双挂载入口、样例流程视图（阶段/评审点/交付物/角色）、样例项目状态视图、两个预置 prompt 模板。
3. 权限：个人模式零入口、无组织上下文零入口（P5-F06），复用 Host Core 权限枚举 `space.read`，不新增权限点。
4. 失败隔离（P5-F07）：插件为纯数据 + 纯函数导出，无 IPC、无网络调用、无全局副作用；渲染异常可被捕获且不影响模块其余能力（集成用例断言）。真机禁用/渲染失败属 B 类。
5. §4.5.3「明确不做」逐条核查通过：无流程引擎、无审批流、无 PLM/ERP 集成、无甘特图排程、无复杂表单建模。
6. 裁决：批次 6 自动化退出条件成立；真机 GUI 与客户真实口径登记 B/C 类，**不宣称批次 6 真机全绿**。

## 2. §4.5.4 四条验收证据

| # | 验收 | 证据 | 判定 |
| --- | --- | --- | --- |
| 1 | 授权用户可打开 IPD Demo 页面 | `docs/IPD入口_T-080.md`；`verify_t080_ipd_entry.py` = 6 [OK]；集成用例「授权用户可打开 IPD Demo 页面」 | 通过（自动化；真机 B 类） |
| 2 | 可看到样例流程的阶段、角色、评审点和交付物 | `docs/IPD流程视图_T-081.md`；`verify_t081_ipd_process.py` = 5 [OK]；集成用例断言四要素文本 | 通过 |
| 3 | 可展示至少一个样例项目的状态 | `docs/IPD项目视图_T-082.md`；`verify_t082_ipd_project.py` = 5 [OK]；集成用例断言当前阶段与项目名 | 通过 |
| 4 | Demo 插件不可用时其他插件与会话不受影响 | 本报告 §3 隔离核查；集成用例「Demo 插件故障被隔离」；P1~P4 回归全绿 | 通过（自动化口径；真机 B 类） |

## 3. 附加核查

| 范围 | 结论 |
| --- | --- |
| P5-F06 权限 | 个人模式零入口；无组织上下文零入口；角色判定复用 `space.read` |
| P5-F07 失败隔离 | 无 IPC / 无网络调用 / 无全局副作用；渲染异常可捕获且模块其余能力可用 |
| §4.5.3 明确不做 | 流程引擎 / 审批流 / PLM-ERP / 甘特图排程 / 复杂表单建模 均无命中 |
| §5.2 插件声明 | `type: ui` + 官方 `dsh.bundle.patch` + 三个槽位 + `space.read` |
| §11 负向清单 | 无第二套插件机制、无自建内核、无移动端等（本插件零新增机制） |

## 4. 验证证据表

| # | 命令 | 结果 |
| --- | --- | --- |
| V-1 | `python scripts/verify_t083_p5.py` | **10 [OK] / 0 [FAIL]** |
| V-2 | `pytest services/api/tests -q` | **78 passed** |
| V-3 | TypeScript 全量回归 | contracts / host-core / plugin-runtime / kernel-dsh / enterprise-admin / knowledge / docgraph / ipd 均 exit 0 |
| V-4 | `python scripts/check_task_split.py --stats` | **8 [OK] / 0 [FAIL]** |

## 5. 未验证项与边界

**需真机复核（B 类）**

- B-1：真机确认个人模式不可见、企业模式可见（菜单与项目空间入口）。
- B-2：真机页面渲染与官方 UI 槽位适配（流程视图、项目视图、示例数据标注）。
- B-3：真机禁用 IPD 插件后其他插件与会话仍可运行。

**需外部输入（C 类）**

- C-1：客户真实 IPD 阶段命名、交付物与角色口径。
- C-2：官方 UI 槽位协议最终形态与菜单注册方式。

**超出本次范围**

- O-1：不做真实 IPD 工作流引擎、审批流、PLM/ERP 集成、多项目甘特图与资源排程、复杂表单建模（§4.5.3）。
- O-2：不接真实项目管理系统、不新增插件管理 IPC。

## 6. 复现命令

```powershell
cd "<repo-root>"
python scripts/verify_t083_p5.py
python scripts/check_task_split.py --stats
pnpm --filter @worknexus/plugin-ipd test
```

## 7. 下一步

1. 批次 4~6 全部完成；后续可推进批次 7（T-090~T-093 P6A ACP，依赖 T-076）与批次 8（T-100~T-105 P6B 插件市场与企业治理）。
