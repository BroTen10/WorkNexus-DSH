/**
 * 把 `src/**` 下的非 TS 资产（如 *.json）按相对路径复制到 `dist/**`。
 *
 * 为什么需要：插件以 `tsc` 产出 JS，但 tsc 不会复制 JSON 等资产；而运行时
 * （打包后的 DSH profile）只消费 `dist/`，缺失资产会让插件在启动时解析失败。
 * 用法（在各插件目录内）：`node ../../scripts/copy_src_assets.mjs`
 */

import { copyFileSync, mkdirSync, readdirSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'

const SOURCE = join(process.cwd(), 'src')
const TARGET = join(process.cwd(), 'dist')
const EXTENSIONS = ['.json']

/** 递归收集需要复制的资产，保持相对路径。 */
function collect(directory) {
  const found = []
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) found.push(...collect(path))
    else if (EXTENSIONS.some(extension => entry.name.endsWith(extension))) found.push(path)
  }
  return found
}

const assets = collect(SOURCE)
for (const asset of assets) {
  const destination = join(TARGET, relative(SOURCE, asset))
  mkdirSync(dirname(destination), { recursive: true })
  copyFileSync(asset, destination)
}

console.log(`copied ${assets.length} asset(s) from src/ to dist/`)
