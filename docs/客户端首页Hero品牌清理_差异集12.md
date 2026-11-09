# 客户端首页 hero 品牌清理（差异集 12 / T-117）交付说明

> **来源**：批次 11 卡 **T-117**（`内部派发卡` §T-117）+ 决策人 2026-10-07 指令（对话界面 DS 标志替换为企业方 LOGO + 按项目概念定口号）→ DC-12（`内部准入评审记录`）
> **权威枚举**：`patches/diffset-12-hero-brand.patch`（14 文件 / 15,683 字节）+ 差异集 03 重导出（24 文件 / 49,730 字节）
> **门禁**：`python scripts/verify_diffset12_hero_brand.py` = **14 [OK] / 0 [FAIL]**
> **登记**：`docs/差异集清单.md` §12、DS-9、DS-10

> **与卡面的对齐**：产出物与 T-117 一致（差异集 12、`scripts/verify_diffset12_hero_brand.py`、本说明）。S1 替换物与文案由决策人在 2026-10-07 指令中给出（标志 = T-107 已落地的企业标志，文案 = 决策人自提「智能协作中心」）；S3 的「用例数不变」已实测（见 V-6）；**S2 的落点偏好已按裁决 A-1 调整**（改用「品牌包占用上游插槽」而非「改 `ui-conversation` 自身组件」），理由与代价见 §7 A-1。

## 1. 结论先行

1. **首屏标志已换**：会话首屏（新会话 hero）此前的上游鲸鱼标志改由本方品牌包的**企业方标志**渲染，与侧栏同一枚素材（决策人 2026-09-30 提供的 128×128 透明 PNG，data URI 单一来源）。
2. **换法遵守上游优先（G0）**：hero 标志本就由上游声明的 `conversation.hero.brand.mark` 插槽渲染（`kind: single` / `scope: root` / `replaceRisk: none`、**无占用者**），因此只在本方 `ui-brand-official` 注册占用；**上游组件 `EmptyHero.tsx` 与其动画鲸鱼回退逐字节未动**，未占用时仍走官方实现。
3. **口号已落地**：首屏标题 `hero.headline` 由上游口号 `探索未至之境` / `Into the Unknown` 改为 **`智能协作中心` / `Intelligent Collaboration Hub`**（决策人自提概念的字面落地：Work + Nexus → 协作 + 中心）。
4. **改动面**：差异集 03 折入并重导出（品牌包 2 文件 + 其 1 个用例期望，**枚举仍 24 文件**）+ 新增差异集 12（14 文件：口号文案源 + 13 个上游期望资产）；上游差异集条目数 **91 → 105**。
5. **验证**：新门禁 14 [OK] / 0 [FAIL]（含真实执行上游用例、补丁可逆重放、条目数）；`t021` 11 [OK]、`t107 --no-artifact` 12 [OK]、`t108` 8 [OK]、差异集 11 门禁 15 [OK]、拆分门禁 8 [OK] 全绿；类型 `tsc -b --force` 与 `oxlint` 退出码 0。
6. **未做**：安装包真机复核（B 类，见 §4）；首屏「预览版」徽标（`hero.preview`）不属本次范围。
7. **诚实登记**：本轮全量复跑发现 **4 条既有红灯**（`t022` U1/U3、`t025` M1、`t028` R2 派生），全部来自更早落地的差异集（03/08/09 与 T-110），**与差异集 12 无关**，详见 §4.4。

## 2. 改动清单

### 2.1 差异集 03（折入并重导出；枚举不变，24 文件）

| # | 文件 | 改动 |
| --- | --- | --- |
| 1 | `packages/client/ui-brand-official/src/client/Brand.tsx` | 抽出 `BrandMark({ size, className })`（供 hero 槽使用）；`OfficialBrandMark` 改为委托它；标志素材仍是**唯一**一处 `BRAND_MARK_DATA_URI` |
| 2 | `packages/client/ui-brand-official/src/client/index.ts` | official 档内新增 `ctx.slots.inject('conversation.hero.brand.mark', …)`；类型侧引用 conversation 契约使插槽名并入类型表 |
| 3 | `packages/client/ui-brand-official/tests/browser-plugin.client.spec.tsx` | 原「hero 保持上游回退」断言**反转**为「hero 由企业标志占用」；新增占用者渲染断言（尺寸/宿主 class/`aria-label`/PNG data URI/无 `path`）；`HOLES` 纳入 hero 槽 |

### 2.2 差异集 12（新增；14 文件）

| # | 文件 | 改动 |
| --- | --- | --- |
| 4 | `packages/client/ui-conversation/src/client/locales.ts` | `hero.headline`：zh `探索未至之境` → `智能协作中心`；en `Into the Unknown` → `Intelligent Collaboration Hub` |
| 5 | `packages/client/ui-conversation/tests/skeleton.client.spec.tsx` | 期望串同步（zh ×3、en ×1） |
| 6–12 | `apps/web/tests/{connection-recovery,details-session-lifecycle,goal-command-presentation,hmr-live,lifecycle-chrome,session-replay-reload,startup-auto-selection}.e2e.ts` | 期望串同步（含 `hmr-live` 的源码 needle，须与新文案一致，否则该用例自身报错） |
| 13–17 | `snapshots/web/{fresh-round-trip/blank-reload,lifecycle-chrome/hero,lifecycle-chrome/plan-active,lifecycle-chrome/plan-active-zh,voice-input/ui}.expected.md` | 快照串同步 |

### 2.3 明确**不改**的部分

- `packages/client/ui-conversation/src/client/skeleton/EmptyHero.tsx`、`HeroShell.module.css`：上游动画（SMIL 形变 + hover 摆动）与排版原样保留；占用者会自然继承宿主 `.fish` 的几何与 hover 动画 class。
- `hero.preview`（「预览版」徽标）：属上游产品阶段标记，另议。
- `package.json` / `pnpm-lock.yaml`：类型侧走 `tsconfig.base.json` 既有 path 映射，**不新增依赖**，故 `verify_t020_build.py` 的锁哈希不变。
- `apps/web/public/manifest.webmanifest` 等 Web 前端静态资源（桌面发行版不加载）。

### 2.4 门禁与登记侧（非上游）

`scripts/verify_diffset12_hero_brand.py`（新增）、`scripts/verify_t021_brand.py`（白名单 +14）、`scripts/verify_t025_model_policy.py`（M5 许可清单 +2 与条目数）、`scripts/verify_t028_release.py`（白名单 +14、条目数、**R6 判据校正**）、`scripts/verify_t109_profile_backfill.py` 与 `scripts/verify_diffset11_cli_shell.py`（条目数）、`docs/差异集清单.md`（§1 表 + §12 + DS-9/DS-10 + 复现命令）、`内部准入评审记录`（DC-12）、`docs/开发文档索引.md`、`内部执行账本`。

## 3. 验证证据表

| # | 检查项 | 命令 / 证据 | 结果 |
| --- | --- | --- | --- |
| V-1 | 差异集 12 门禁 | `python scripts\verify_diffset12_hero_brand.py` | **14 [OK] / 0 [FAIL]**（P1 枚举 14、P2 插槽占用与素材单一来源 ×4、P3 上游组件零改动 ×2、P4 上游用例全绿、P5 口号 ×2、P6 期望同步、P7 条目数 105 + 落点齐备、P8 补丁可逆重放） |
| V-2 | 品牌差异集回归 | `python scripts\verify_t021_brand.py` | 11 [OK] / 0 [FAIL]（G2 白名单覆盖新增 14 条） |
| V-3 | 客户端品牌门禁 | `python scripts\verify_t107_client_brand.py --no-artifact` | 12 [OK] / 0 [FAIL]（P2 枚举与重导出后的 03 补丁一致） |
| V-4 | 差异集 11 门禁 | `python scripts\verify_diffset11_cli_shell.py` | 15 [OK] / 0 [FAIL]（含 P7 条目数 105） |
| V-5 | 拆分自洽门禁 | `python scripts\check_task_split.py --stats` | 8 [OK] / 0 [FAIL]（85 张卡，含本条的 T-117） |
| V-6 | 上游用例（插槽注册 + hero 渲染 + 文案） | `pnpm exec vitest run packages/client/ui-brand-official/tests/browser-plugin.client.spec.tsx packages/client/ui-conversation/tests/skeleton.client.spec.tsx` | **2 文件 / 32 用例全通过**；**用例数不变**（`it(` 计数：品牌包 6 → 6、ui-conversation 26 → 26），符合 T-117 S3 口径 |
| V-7 | 类型 | `pnpm exec tsc -b packages/client/ui-brand-official/tsconfig.json --force` | exit 0（跨包类型引用经 `tsconfig.base.json` path 映射解析，无新增依赖） |
| V-8 | Lint | `pnpm exec tsx scripts/run-oxlint.ts <3 个改动文件/目录>` | exit 0 |
| V-12 | 客户端回归门禁（T-117 验证行） | `python scripts\verify_t108_client_regression.py` | 8 [OK] / 0 [FAIL]（上游桌面壳套件全绿、用例声明零减少、品牌串仅存于登记的自洽夹具） |
| V-9 | 补丁枚举与体积 | `Get-Content patches\diffset-12-hero-brand.stat.txt` | 14 文件 / 24 插入 / 24 删除；补丁 15,683 字节；03 重导出 24 文件 / 49,730 字节（原 45,118） |
| V-10 | 条目数一致性 | `verify_diffset12_hero_brand.py` P7 / `git diff --name-only` + 未跟踪 | 91 → **105**（补丁去重后与工作区改动集逐条一致） |
| V-11 | 品牌合规面 | `verify_t107_client_brand.py` P3~P5（闭包） | 客户端源码品牌残留 0（本次未新增 `DeepSeek Harness` 文案；hero 口号为自有文案） |

## 4. 未验证项与边界

### 4.1 需真机复核（B 类）

| # | 项 | 判据 |
| --- | --- | --- |
| B-1 | 安装态首屏实际渲染（T-117 验证行的 asar 部分） | 重出包并覆盖安装后打开「新会话」：首屏标志为企业方标志、标题为「智能协作中心」。自动化侧只证明「插槽在 official 档被占用 + 占用者渲染出 PNG 标志」，**未证明**打包后的客户端构建图内含该注册（`verify_t111`/`verify_t112` 的端到端探针可顺带断言） |
| B-2 | 视觉与主题 | 34px 标志与 26px 标题的基线对齐、深浅两套主题下的观感（素材透明底、彩色，深色下不依赖 `currentColor`） |
| B-3 | hover 行为 | 占用者继承宿主 `.fish` 的 hover 摆动动画（旋转/位移），需确认对位图标志无违和 |

### 4.2 需外部输入（C 类）

| # | 项 | 说明 |
| --- | --- | --- |
| C-1 | 口号定稿 | 本次按决策人自提概念落地为「智能协作中心」。若改选其他候选，**只需改 `locales.ts` 两行 + 同步 13 个期望资产**（共 14 文件，脚本化 1 分钟内可重放） |
| C-2 | 「预览版」徽标是否保留 | 截图红框同时框住了该徽标；上游文案为 `hero.preview`，本次未动 |

### 4.3 超出本次范围

- `apps/web` 的 Playwright e2e（`apps/web/tests/*.e2e.ts`）与 `snapshots/web/**` 在本机**未执行**（需浏览器与 dev server）：本次只按 DS-3 就地同步其期望串，未运行回归。
- 上游 `CONTRIBUTING.zh.md` 中的同名字样是上游文档正文（非产品可见面），按「不扩大差异集」原则未改。

### 4.4 既有红灯登记（非本次引入）

本轮全量复跑（`verify_t028_release.py` = 30 [OK] / 4 [FAIL]）暴露 4 条既有红灯，**全部由更早落地的差异集遗留**，差异集 12 未触及它们的判据输入：

| # | 门禁 | 现象 | 根因（判定依据） |
| --- | --- | --- | --- |
| E-1 | `verify_t022_update.py` U1 | 「上游更新/签名机制文件零改动」命中 `apps/desktop/installer/uninstall.nsh`、`apps/desktop/scripts/desktop-auto-update-environment.mjs`、`apps/desktop/scripts/installer.nsh`、`apps/desktop/src/main.ts` | 守卫自差异集 03/08/09 落地后未同步（四者分别属 03/08/09） |
| E-2 | `verify_t022_update.py` U3 | `production` 更新源 `publicUrl = None`（断言仍期望上游 `https://download.deepseek.com/dsh-desk/feeds/win-x64/`） | 差异集 08 已生产 origin 改为环境驱动（`DOWNLOAD_PROD_ORIGIN`），旧断言与新实现互斥 |
| E-3 | `verify_t025_model_policy.py` M1 | 断言要求组建行含带引号的包名 `'@worknexus/ent-core/model-policy'` | T-110（`5223f18`，2026-10-07）已按上游 Loader 要求把组建行改为**相对路径** `'./model-policy.js'`；`bundles/**` 本轮零改动（`git status` 两仓均无 `bundles/` 命中），故红灯先于本次存在 |
| E-4 | `verify_t028_release.py` R2 | 「有可执行证据的验收项其门禁本轮已跑绿」缺 2 项（升级演练） | E-1/E-2 的派生结果 |

> 共同性质：三条断言都**绑定实现形状**（文件零改动清单、域名字面量、包名字面量）而非语义（更新机制未被接管、更新源非空且企业可控、组建行可被 Loader 装载）。建议单独一次「门禁判据校正」，本轮不擅自扩大范围。

## 5. 复现命令

```powershell
cd "<repo-root>"

# 差异集 12 权威枚举与体积
Get-Content patches\diffset-12-hero-brand.stat.txt
Get-Content patches\diffset-03-client-brand.stat.txt

# 新门禁（含上游用例回归；--no-suite 可跳过用例）
python scripts\verify_diffset12_hero_brand.py

# 相关回归
python scripts\verify_t021_brand.py
python scripts\verify_t107_client_brand.py --no-artifact
python scripts\verify_diffset11_cli_shell.py
python scripts\check_task_split.py --stats

# 上游用例（插槽占用 + hero 文案）
cd repos\deepseek-harness
pnpm exec vitest run packages/client/ui-brand-official/tests/browser-plugin.client.spec.tsx packages/client/ui-conversation/tests/skeleton.client.spec.tsx

# 类型与 lint
pnpm exec tsc -b packages/client/ui-brand-official/tsconfig.json --force
pnpm exec tsx scripts/run-oxlint.ts packages/client/ui-brand-official/src packages/client/ui-brand-official/tests packages/client/ui-conversation/src/client/locales.ts

# 补丁重放（新检出锁定 tag 后，按 01→12 顺序）
git apply --binary --whitespace=nowarn ..\..\patches\diffset-12-hero-brand.patch
```

## 6. 下一步

1. **重出包并真机复核 B-1~B-3**（`python scripts\package_desktop_win_unsigned.py`，约 9 分钟）——这是本条目唯一的验收缺口。
2. **口号定稿**：若采用其他候选（或去掉「预览版」徽标），按 C-1/C-2 走一次 14 文件重放即可，无需重建差异集结构。
3. **建议单独立项「门禁判据校正」**：修 E-1~E-4 三条断言绑定实现形状的既有红灯（语义判据见 §4.4 引述），使 `t022`/`t025`/`t028` 回到全绿。
4. 上游下一次同步时，注意 `ui-conversation` 的 hero 文案与 `conversation.hero.brand.mark` 插槽声明属本差异集触点（重放顺序见 §5）。

## 7. 裁决记录

| # | 裁决：<决定> — <理由> — <错判代价> |
| --- | --- |
| A-1 | **用插槽占用换标志，不替换上游回退实现** — hero 标志本就是上游声明的单占用槽（`replaceRisk: none`、无占用者），占用是官方扩展点，能同时保住上游动画回退与「不篡改上游组件」的 G0 要求 — 若直接改 `EmptyHero.tsx` 内联企业方素材：上游组件被改、动画与素材耦合、每次同步要重解冲突，且把品牌素材复制进第二个包（代价：一次插槽注册 + 类型侧引用） |
| A-2 | **品牌包两文件折入差异集 03 并重导出，hero 文案另立 12** — 同一文件出现在两个补丁会让 3-way 重放互相冲突（DS-8 同口径）；`ui-conversation/locales.ts` 是新文件，属新条目 — 若不折入：03 与 12 都改动 `ui-brand-official/src/client/index.ts`，重放顺序错一次就会得到半套品牌面 |
| A-3 | **口号中英同步替换** — 插槽与文案都面向企业发行版，en 保留上游口号（`Into the Unknown`）等于承认英文界面仍有上游品牌面 — 若只改 zh：中英界面品牌不一致，且下次同步时 en 文案更易漏改（代价：多同步 8 个 e2e + 4 个快照） |
| A-4 | **上游期望就地更新，不新建 overlay** — 沿用 `docs/差异集清单.md` §3 的全局裁决（DS-3）与 DC-7 口径：只改期望值，不改测试逻辑 — 若改用「不跑/跳过」：违反 AGENTS §6，且回归网失效（代价：一次 13 文件期望同步） |
| A-5 | **`verify_t028_release.py` 的 R6 判据由「用例声明未增删」校正为「用例声明未减少」** — 旧判据把标题文本当用例身份，会迫使改动者保留语义已假的用例名（本次即 `leaves the conversation hero on its declaring fallback` → `fills the blank-session hero mark`），AGENTS §6 保护的是「不得删除或跳过」；判据改为逐 spec 统计声明增删行数（净减少即 [FAIL]），删测试文件与新增 skip/todo 两条负向断言不变 — 若沿用旧判据：门禁奖励「改行为不改名字」的隐真，且每一次品牌口径更新都要额外付一次门禁口径争论（代价：一次判据重写 + 本轮全量复跑） |
