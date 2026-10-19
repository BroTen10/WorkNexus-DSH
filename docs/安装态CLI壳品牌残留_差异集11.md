# 安装态 CLI 壳品牌残留 — 差异集 11

> 条目：差异集 11 ｜ 批次 10 附带项（`docs/待办清单-批次10企业入口最小闭环.md` §3 待办 6）｜ 执行日期：2026-10-07
> 性质：与差异集 01/04 同类的**品牌承载资产**（上游写死产品名的 launcher 资产），位于 `app.asar` 之外，
> 因此 T-107 的 `app.asar` 品牌统计覆盖不到它。

## 1. 结论先行

1. **现象与根因**：安装态 `resources/runtime/cli/bin/dsh.cmd` 由 `apps/desktop/cli/dsh.cmd`
   原样拷贝而来，资产里写死 `DeepSeek Harness.exe`；本发行版的可执行文件已改名
   `WorkNexus-DSH.exe`（T-107），因此该 CLI 壳**必然失败**：
   `'...DeepSeek Harness.exe' is not recognized`（exit 9009）。
2. **修复方式 = 模板化 + 单一来源**：两个 launcher 资产改为携带占位符
   `__DSH_DESKTOP_PRODUCT_NAME__`，由 `apps/desktop/scripts/prepare-cli.ts` 在打包时
   用产品名单一来源 `desktop-product-name.mjs`（T-107 S4 建立）替换后写出。
   占位符缺失时 fail loud，绝不静默拷回上游名。
3. **同类缺陷一并修掉**：macOS 资产 `apps/desktop/cli/dsh` 有同一个写死上游名的缺陷
   （`.../MacOS/DeepSeek Harness`），本条目一并修正 —— 只修 Windows 会留下同源的 macOS 缺口。
4. **上游夹具同步**：`apps/desktop/tests/cli-launcher.spec.ts` 自建的可执行名改为引用同一常量
   （原为上游名为夹具输入）；该用例实测 **1 passed / 1 skipped**，测试逻辑与用例数不变。
   退出 `verify_t108_client_regression.py` 的「自洽夹具」允许集合（P5 是「只允许集合内命中」，
   移除不放宽判据）。
5. **差异集 11 = 6 个上游文件**（25 插入 / 7 删除 / 5,835 字节）；上游差异集条目数 85 → 91。
   **扩项（2026-10-07，决策人「清理残余」）**：CLI 自身 `--help` 的描述文案（`apps/cli/src/args.ts`：
   `dsh: boot a DeepSeek Harness profile …` → `… WorkNexus-DSH …`）与其上游文件快照
   `apps/cli/tests/expected/launcher-help.txt`（由 `apps/cli/tests/built-bin.e2e.ts` 快照比对，实测 1 passed）。

## 2. 改动清单

| 类型 | 路径 | 说明 |
| --- | --- | --- |
| 修改（上游资产） | `repos/deepseek-harness/apps/desktop/cli/dsh.cmd` | 可执行名 → 占位符（保留 CRLF） |
| 修改（上游资产） | `repos/deepseek-harness/apps/desktop/cli/dsh` | macOS launcher 可执行名 → 占位符 |
| 修改（上游脚本） | `repos/deepseek-harness/apps/desktop/scripts/prepare-cli.ts` | 读模板 → 用 `DESKTOP_PRODUCT_NAME` 替换 → 写出；占位符缺失即报错 |
| 修改（上游测试） | `repos/deepseek-harness/apps/desktop/tests/cli-launcher.spec.ts` | 夹具可执行名改为引用 `DESKTOP_PRODUCT_NAME` |
| 修改（上游 CLI） | `repos/deepseek-harness/apps/cli/src/args.ts` | `--help` 描述文案 → `boot a WorkNexus-DSH profile …` |
| 修改（上游期望） | `repos/deepseek-harness/apps/cli/tests/expected/launcher-help.txt` | 该文案的上游文件快照同步 |
| 差异集 | `patches/diffset-11-cli-shell.patch` + `.stat.txt` | 权威枚举（6 文件 / 5,835 字节） |
| 门禁 | `scripts/verify_diffset11_cli_shell.py` | 7 组断言 / 13 项（含真实 `prepareDesktopCli` 行为探针与上游用例回归） |
| 门禁回归 | `scripts/verify_t021_brand.py`、`verify_t025_model_policy.py`、`verify_t028_release.py`、`verify_t108_client_regression.py`、`verify_t109_profile_backfill.py` | 白名单与条目数 85 → 89；`cli-launcher` 退出自洽夹具清单 |

**裁决：把 launcher 改成模板 + 占位符，而不是在资产里直接写死本发行版名 — 理由：待办清单明确要求
「改为引用产品名单一来源（对齐 T-107 S4 的 desktop-product-name.mjs）」；直接写死会让产品名出现
第二、第三处，下一次改名又会漏检 — 错判代价：多一个由 `prepare-cli.ts` 承担的替换步骤，
因此加了「占位符缺失即抛错」的断言防止静默回退。**

**裁决：一并修 macOS `cli/dsh` 资产 — 理由：同一生成链路（`prepareDesktopCli`）、同一缺陷形态，
只修 Windows 会让 macOS 安装包继续指向不存在的二进制 — 错判代价：差异集多 1 个文件；
该文件的验收证据为行为探针（macOS 产物指向 `WorkNexus-DSH`），未在 macOS 真机执行。**

**裁决：`cli-launcher.spec.ts` 就地更新夹具（退出 T-108 的自洽夹具允许集合） — 理由：该夹具的
可执行名不再是「测试自建的形态输入」而是**产品名的事实**，继续保留上游名会让上游用例与本发行版
行为不一致（用例会红）；按 DC-7「期望值/夹具随差异集补丁走」的同一口径就地处置 —
错判代价：`verify_t108_client_regression.py` 的允许集合少一项，需与该门禁同步修改（已改）。**

## 3. 验证证据表

| 门禁 | 命令 | 结果 |
| --- | --- | --- |
| 差异集 11 | `python scripts/verify_diffset11_cli_shell.py` | **13 [OK] / 0 [FAIL]** |
| 上游用例 | `vitest run --project thread-safe apps/desktop/tests/cli-launcher.spec.ts` | **1 passed / 1 skipped** |

行为探针（P4）实测：`prepareDesktopCli(win32)` 产物含 `WorkNexus-DSH.exe`、
`prepareDesktopCli(darwin)` 产物含 `MacOS/WorkNexus-DSH`，两者都不含上游产品名。

## 4. 未验证项与边界

- **已由 T-112 关闭（自动化）**：安装态 `resources/runtime/cli/bin/dsh.cmd` 实测 `--help` exit 0 并打印用法
  （`verify_t112_enterprise_acceptance.py` A4）。
- **超出本次范围**：macOS 真机执行 `/usr/local/bin/dsh`（本机为 Windows）。
- **边界**：`link-entry.c`（macOS 命令链接辅助程序）与命令管理对话框的文案不含产品名，未在本条目内改动。

## 5. 复现命令

```powershell
cd "<repo-root>"
python scripts\verify_diffset11_cli_shell.py
python scripts\verify_diffset11_cli_shell.py --no-suite   # 只跳过上游用例回归
# 差异集重导出
git -C repos\deepseek-harness diff --binary -- apps/desktop/cli/dsh apps/desktop/cli/dsh.cmd `
  apps/desktop/scripts/prepare-cli.ts apps/desktop/tests/cli-launcher.spec.ts
```

## 6. 下一步

1. T-112 真机验收：重出包并安装后执行 `dsh.cmd`，核对「打印用法」与「无 9009」。
2. 待办 7：`docs/差异集清单.md` 新增条目 10/11、`内部准入评审记录` 登记 DC-11、
   账本与总览回写。
