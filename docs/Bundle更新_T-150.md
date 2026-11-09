# Bundle 更新（T-150）

## 1. 结论先行

五个 Bundle 根已刷新到当前兼容版本：

| Bundle | 旧版本 | 新版本 |
| --- | --- | --- |
| `dshmarket` | 1.66.45 | **1.73.7** |
| `dsh-better-sidebar` | 0.28.0 | **0.28.2** |
| `dsh-claude-style` | 0.18.1 | **0.19.6** |
| `@linxin666/dsh-client-ui-skill-explorer` | 0.4.8 | **0.4.13** |
| `@tt-a1i/archify-dsh` | 1.0.0 | 1.0.0（保持） |

锁文件、依赖闭包、许可证、88 个 tgz、构建运行时、安装态 `app.asar`
与真实 profile 运行态版本一致。最终安装包安装 exit 0，安装态
`FileVersion=0.2.1-rc.5`。
Agent 上下文能力以当前 DSH `0.2.1-rc.5` 为宿主基线，不再保留 rc.2
插件版期望。

## 2. 改动清单

| 范围 | 改动 |
| --- | --- |
| 版本锁 | 4 个 Bundle 根换版；Archify 不变；导出 88 个 tgz = 5 根 + 83 依赖 |
| 许可证 | 新增 4 个新版许可证，移除 4 个旧版许可证 |
| 上游 profile | `profile-bundle-backfill.ts` 四个精确版本锚点更新 |
| 上游测试 | `project-manager.spec.ts` 预置版本期望更新 |
| 差异集 | 07 / 10 / 14 重导出；条目总数保持 120 |
| 门禁 | T-126 / T-143 / T-147 / T-148 期望同步 |
| 声明 | `WORKNEXUS-THIRD-PARTY-NOTICES.md` 重生成，136,890 B |
| 安装包 | `worknexus-dsh-0.2.1-rc.5-win-x64-unsigned.exe` |

新根包 SHA-256：

| Bundle | SHA-256 |
| --- | --- |
| `dshmarket@1.73.7` | `7e9e48b2b4ed…` |
| `dsh-better-sidebar@0.28.2` | `f5ed557f45e9…` |
| `dsh-claude-style@0.19.6` | `de1e95a63273…` |
| Skill Explorer `0.4.13` | `42b2d324eae3…` |
| Archify `1.0.0` | `d009c47…`（未变） |

## 3. 验证证据表

| 验证 | 实测 |
| --- | --- |
| `fetch_third_party_bundles.py --verify-only` | 88 [OK] / 0 [FAIL] |
| `pack_presets.py --verify-only` | 88 [OK] / 0 [FAIL] |
| T-020 全量构建基线 | 10 [OK] / 0 [FAIL]；rc.5 归档 |
| T-027 上游同步/升级演练 | 28 [OK] / 0 [FAIL] |
| T-148 / T-150 Bundle 门禁 | 7 [OK] / 0 [FAIL]；含安装态 asar |
| T-126 市场更新路径 | 7 [OK] / 0 [FAIL] |
| T-147 市场更新稳定性 | 5 [OK] / 0 [FAIL] |
| T-143 个人版宿主 | 9 [OK] / 0 [FAIL] |
| T-107 客户端品牌 | 16 [OK] / 0 [FAIL] |
| T-108 桌面壳回归 | 8 [OK] / 0 [FAIL]；1555 tests passed / 64 skipped |
| T-125 默认模型路由 | 36 [OK] / 0 [FAIL] |
| 差异集 14 | 8 [OK] / 0 [FAIL] |
| 差异集全量重放 | 31 [OK] / 0 [FAIL]；120 文件逐字节一致 |
| 出包 | exit 0；330,079,048 B |
| 安装器 SHA-256 | `1CF994BD742179DDD6A17987B9C1395668FA3CD28EB6E34D570271BFB3053746` |
| 安装态 | exit 0；`FileVersion=0.2.1-rc.5` |
| 安装态 asar | 375,987,760 B；SHA-256 `6975DB6DE7326B791838B6388A4D616BA0797F074DD08F568A5FA910EFFC5D9E` |
| 真实 profile 启动补齐 | 安装态客户端启动后，四个 manifest 版本锚点与 `node_modules` 实际版本一致；外部 `dshmarket=1.73.7` |
| 用户配置保留 | `cordis.patch.yml` 启动前后均为 2,546 B；SHA-256 `B1DF6060C7316FD4C3D93A00F70B2AFBFF0B884C193996E7F98B7E7A6A363991`，修改时间未变 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：插件市场页与四个插件页面的逐页 GUI 目视。
- B-2：在 GUI 中完成一次插件禁用/启用、一次真实模型对话和工具调用。

**需外部输入（C 类）**

- C-1：插件兼容性依据 npm `latest`、peer 范围、运行时装配与宿主市场 API
  验证；未逐个执行插件作者的全部 UI 自动化。
- C-2：T-022 的既有 U1/U3 三项更新源边界未改变。

**超出本次范围**

- 不转成企业 profile，不新增企业 bundle。
- 不跟 `0.2.2-alpha.2`。

## 5. 复现命令

```powershell
python scripts\fetch_third_party_bundles.py --verify-only
python scripts\pack_presets.py --verify-only
python scripts\verify_t148_latest_bundles.py --check-npm
python scripts\verify_t126_plugin_update_path.py
python scripts\verify_t147_plugin_update_stability.py
python scripts\verify_t143_personal_only.py
python scripts\verify_diffset14_third_party_notices.py
python scripts\package_desktop_win_unsigned.py
```

## 6. 下一步

1. 人工完成 B-1/B-2。
2. 重新生成并审计脱敏公开快照；不发布本仓内部历史与过程记录。
3. 下一轮 Bundle 跟版继续使用锁定 tgz、许可证和 `--check-npm` 门禁。

## 7. 裁决记录

- **四个有更新的根全部跟到 npm `latest`，Archify 保持 1.0.0** — 与用户
  “更新 Bundle 插件版本”一致，Archify 已是最新 — 错判代价是遗漏上游新版。
- **不保留旧版 tgz / 许可证** — 88 条锁文件必须与包集完全一一对应 —
  错判代价是新机仍可能选中旧包。
- **安装态 asar 纳入门禁** — 只检查构建运行时无法证明安装包内含新版 —
  错判代价是交付旧 Bundle 而不自知。
