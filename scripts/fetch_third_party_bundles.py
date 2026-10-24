#!/usr/bin/env python
"""按锁文件取回随发行版预置的第三方 DSH bundle（含运行依赖闭包）。

覆盖两批预置：T-120 的插件市场 `dshmarket`（+ `undici`），以及决策人指定的
**随发行版默认启用的市场插件**（`dsh-better-sidebar` / `dsh-claude-style` /
`@tt-a1i/archify-dsh` / `@linxin666/dsh-client-ui-skill-explorer`）。四个插件的客户端半边**自带打包**（mermaid 7 MB、
CodeMirror 2 MB 等依赖已内联进 `lib/client*.js`），宿主半边只引用桌面运行时已随包的模块，
因此本体随包即可，无需额外的运行依赖（证据见 `docs/插件预置_差异集02-10.md`）。

`--add <name>@<version>` 是**登记入口**：从 npm registry 读该精确版本的 tarball 地址与许可证，
下载后算出 `bytes` / `sha256` 写入锁文件，并把许可证原文落盘到 `configs/vendor/licenses/`；
随后照常取回到包集目录。锁文件因此始终是「版本 + 哈希 + 许可证」的唯一来源。

为什么需要本脚本：上游 `prepare-package-set.ts` 的包集闭包只从**目录里的 tgz** 推导
（`packedPackages(inputs)`），闭包对「未随包提供的依赖」只在它是上游 workspace 包时才报错，
其余**静默跳过** —— 也就是说，若只放 `dshmarket` 的 tgz，它的 `undici` / `js-yaml`
会在 profile 安装时被要求**联网解析**。企业内网安装必须离线可用，因此这里把
dshmarket 及其运行依赖一并钉死版本与 sha256 后放进包集目录。

规范化（`normalization`，确定性重打包，锁文件同时登记 `sha256` 上游原样与 `normalizedSha256` 发布产物）：
  - `strip-dotfile-placeholders`：上游 npm tarball 里可能带 `.gitkeep` 之类的**占位 dotfile**，
    而 electron-builder 打包 asar 时会丢弃它们 —— 于是「准备目录生成的完整性清单」与「打包后的 asar」
    差一个文件，末步冒烟报 `desktop runtime: ASAR integrity verification failed`
    （2026-10-07 实测：唯一差异就是 `undici/lib/llhttp/.gitkeep`）。
  - `package-root-prefix`：DefinitelyTyped 发布的 `@types/*` 归档用**去 scope 后的包名**作根目录
    （`d3/`、`d3-array/`…），而 `packedManifest()` 与 pnpm 都只认 `package/package.json`
    —— 原样随包会让 `prepare:packages` 直接报 `tar: package/package.json: Not found in archive`
    （2026-10-09 实测于 `@types/d3`）。该规则的包由 `--add` 自动标记。

纪律：
  - 版本与 sha256 唯一来源是 `configs/vendor/third-party-bundles.lock.json`；
  - 已存在且哈希匹配的文件**不重复下载**（幂等、可离线重跑）；
  - 哈希不匹配一律 [FAIL] 并删除坏文件，绝不静默使用。
  - 声明了规范化规则但锁文件缺 `normalizedSha256` 时**失败**并打印实测值，避免"未登记即发布"。

用法：
  python scripts/fetch_third_party_bundles.py                     # 取到 .worknexus-packed/
  python scripts/fetch_third_party_bundles.py --out .worknexus-packed
  python scripts/fetch_third_party_bundles.py --verify-only       # 只校验不下载
  python scripts/fetch_third_party_bundles.py --add dsh-better-sidebar@0.28.0

退出码：全部就绪为 0；任一缺失/不匹配为 1。
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import json
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / "configs" / "vendor" / "third-party-bundles.lock.json"
LICENSES = REPO / "configs" / "vendor" / "licenses"
USER_AGENT = "worknexus-dsh-vendor/1.0"
# tarball 里许可证原文的候选文件名（大小写不敏感）。
LICENSE_NAMES = ("license", "license.md", "license.txt", "licence", "licence.md", "copying")


def license_stem(name: str, version: str) -> str:
    """许可证原文的落盘名（scoped 包的 `/` 换成 `-`，与声明生成器一致）。"""
    return f"{name.replace('/', '-')}-{version}"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310 - 锁文件里的固定 https 地址
        destination.write_bytes(response.read())


def registry_metadata(name: str, version: str) -> dict:
    """读 npm registry 的某个精确版本（只取登记所需字段）。"""
    url = f"https://registry.npmjs.org/{name.replace('/', '%2f')}/{version}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - 固定 https 地址
        return json.loads(response.read().decode("utf-8"))


def extract_license(tarball: Path, name: str, version: str) -> Path:
    """从 tarball 取出许可证原文并落盘；登记进锁文件的包没有原文即失败（不静默放过）。"""
    found: tuple[str, bytes] | None = None
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            base = member.name.rsplit("/", 1)[-1].lower()
            if base not in LICENSE_NAMES:
                continue
            payload = archive.extractfile(member).read()
            found = (member.name, payload)
            if member.name.count("/") <= 1:
                break
    if found is None:
        raise SystemExit(f"{name}@{version}: tarball 里找不到许可证原文，登记中止（许可证需人工确认）")
    LICENSES.mkdir(parents=True, exist_ok=True)
    target = LICENSES / f"{license_stem(name, version)}.LICENSE.txt"
    target.write_bytes(found[1])
    return target


def add_lock_entry(name: str, version: str, out: Path, role: str, role_label: str | None = None) -> str:
    """登记 name@version：下载 → 算哈希 → 落盘许可证 → 写锁文件 → 放进包集目录。"""
    metadata = registry_metadata(name, version)
    url = str(metadata["dist"]["tarball"])
    basename = url.rsplit("/", 1)[-1]
    # scoped 包的 tarball 名由 npm 去掉 scope 生成（@types/d3 → d3-x.y.z.tgz、@linxin666/x → x-x.y.z.tgz），
    # 会与同名非 scoped 包（d3 与 @types/d3）撞车，因此随包文件名带上 scope 前缀。
    file = basename if not name.startswith("@") else f"{name.split('/', 1)[0][1:]}-{basename}"
    entry = {
        "name": name,
        "version": version,
        "role": role,
        "license": str(metadata.get("license") or "UNKNOWN"),
        "url": url,
        "file": file,
        "bytes": 0,
        "sha256": "",
    }
    # @types/* 的归档根目录不是 package/，必须按规则重写后才能被上游闭包读到。
    if name.startswith("@types/"):
        entry["normalization"] = "package-root-prefix"
    if role_label:
        # 逐条角色说明（进发行版附加声明的「角色」列）：同名角色下语义不同的包必须能分开写。
        entry["roleLabel"] = role_label
    out.mkdir(parents=True, exist_ok=True)
    target = out / entry["file"]
    download(url, target)
    entry["bytes"] = target.stat().st_size
    entry["sha256"] = sha256_of(target)
    if entry.get("normalization") is not None:
        normalized, _ = normalize_tarball(target, entry["normalization"])
        entry["normalizedSha256"] = normalized
    extract_license(target, name, version)

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    kept = [item for item in lock["packages"]
            if not (item["name"] == name and item["version"] == version)]
    kept.append(entry)
    lock["packages"] = sorted(kept, key=lambda item: (item["name"], item["version"]))
    lock["fetchedAt"] = datetime.date.today().isoformat()
    LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rule = entry.get("normalization")
    return (f"{name}@{version} 已登记并取回（{entry['file']}，{entry['bytes']} 字节，"
            f"{entry['license']}，sha256 {entry['sha256'][:12]}…"
            + (f"，规范化 {rule} → {entry['normalizedSha256'][:12]}…）" if rule else "）"))


def normalize_tarball(source: Path, mode: str) -> tuple[str, int]:
    """按登记规则确定性重打包，返回（新 sha256, 字节数）。

    支持的规则：
      - `strip-dotfile-placeholders`：剔除占位 dotfile（`undici` 的 `.gitkeep` 会被
        electron-builder 丢弃，留着会让 asar 完整性校验失败）。
      - `package-root-prefix`：把归档根目录重写为 `package/`。DefinitelyTyped 发布的
        `@types/*` 归档用**去 scope 后的包名**作根目录（如 `d3/`、`d3-array/`），而上游
        `packedManifest()` 与 pnpm 都只认 `package/package.json`，因此原样随包会在
        `prepare:packages` 阶段直接报 `tar: package/package.json: Not found in archive`。

    确定性来自：保留上游 TarInfo（含 mtime/权限），成员顺序不变，gzip mtime 固定为 0。
    因此同一份上游字节永远得到同一份产物（`sha256` 记上游原样、`normalizedSha256` 记发布产物）。
    """
    strip_dotfiles = mode == "strip-dotfile-placeholders"
    reprefix = mode == "package-root-prefix"
    if not strip_dotfiles and not reprefix:
        raise SystemExit(f"未知的规范化规则: {mode}")
    entries: list[tuple[tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(source, "r:gz") as archive:
        for member in archive.getmembers():
            name = member.name.rsplit("/", 1)[-1]
            # 只剔除「以 . 开头且不是 . / ..」的占位文件；目录与正常文件原样保留。
            if strip_dotfiles and name.startswith(".") and name not in {".", ".."} and member.isfile():
                continue
            if reprefix and not member.name.startswith("package/"):
                member = member.replace(name=re.sub(r"^[^/]+", "package", member.name))
            payload = archive.extractfile(member).read() if member.isfile() else None
            entries.append((member, payload))
    staged = source.with_suffix(".normalized")
    with staged.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as target:
                for member, payload in entries:
                    if payload is None:
                        target.addfile(member)
                    else:
                        import io
                        target.addfile(member, io.BytesIO(payload))
    data = staged.read_bytes()
    staged.replace(source)
    return hashlib.sha256(data).hexdigest(), len(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".worknexus-packed")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--add", action="append", default=[], metavar="NAME@VERSION",
                        help="先登记并取回该精确版本（可重复；写入锁文件与许可证目录）")
    parser.add_argument("--role", default="bundle-root",
                        help="配合 --add 使用的角色标签（bundle-root / runtime-dependency）")
    parser.add_argument("--role-label", default=None,
                        help="配合 --add 使用的逐条角色说明（进发行版附加声明的「角色」列）")
    args = parser.parse_args()
    if args.add and args.verify_only:
        parser.error("--add 会下载并写锁文件，不能与 --verify-only 同时使用")

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    out = (REPO / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("第三方预置 bundle 取回（版本 + sha256 来自锁文件）")
    print("=" * 60)

    for spec in args.add:
        name, _, version = spec.rpartition("@")
        if not name or not version:
            parser.error(f"--add 需要 name@version 形式，收到 {spec!r}")
        print(f"[..] {name}@{version} 登记中（registry → 哈希 → 许可证原文 → 锁文件）")
        print(f"[OK] {add_lock_entry(name, version, out, args.role, args.role_label)}")
        lock = json.loads(LOCK.read_text(encoding="utf-8"))

    failures: list[str] = []
    for entry in lock["packages"]:
        name = f"{entry['name']}@{entry['version']}"
        target = out / entry["file"]
        rule = entry.get("normalization")
        normalizing = rule is not None
        expected = entry.get("normalizedSha256") if normalizing else entry["sha256"]
        if target.exists() and sha256_of(target) == expected:
            print(f"[OK] {name} 已就绪（{target.stat().st_size} 字节，sha256 匹配）")
            continue
        if target.exists():
            print(f"[..] {name} 哈希不匹配，重新取回")
            target.unlink()
        if args.verify_only:
            failures.append(f"{name}: 缺失 {target.name}")
            print(f"[FAIL] {name} 缺失（--verify-only 不下载）")
            continue
        try:
            download(entry["url"], target)
        except Exception as error:  # noqa: BLE001 - 记录原始错误即可
            failures.append(f"{name}: 下载失败 {error}")
            print(f"[FAIL] {name} 下载失败：{error}")
            continue
        actual = sha256_of(target)
        if actual != entry["sha256"]:
            target.unlink()
            failures.append(f"{name}: sha256 不匹配（期望 {entry['sha256']}，实得 {actual}）")
            print(f"[FAIL] {name} sha256 不匹配，已删除坏文件")
            continue
        if normalizing:
            normalized, size = normalize_tarball(target, rule)
            if entry.get("normalizedSha256") != normalized:
                target.unlink()
                failures.append(
                    f"{name}: normalizedSha256 不匹配（期望 {entry.get('normalizedSha256')}，实得 {normalized}）")
                print(f"[FAIL] {name} 规范化后哈希未登记或与锁文件不一致："
                      f"normalizedSha256 = {normalized}（{size} 字节）")
                continue
            print(f"[OK] {name} 取回 + 规范化（{rule}，{size} 字节）")
        else:
            print(f"[OK] {name} 取回并校验（{entry['bytes']} 字节）")

    print("-" * 60)
    print(f"结果: {len(lock['packages']) - len(failures)} [OK] / {len(failures)} [FAIL]")
    for detail in failures:
        print(f"  - {detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
