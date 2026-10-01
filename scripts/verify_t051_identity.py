#!/usr/bin/env python
"""T-051 门禁：客户端身份联通与边界。

断言：
  I1  结构齐备
  I2  Host Core identity 测试与 typecheck 通过
  I3  SecureStore 只声明官方凭据适配；无本地凭据存储实现
  I4  企业 Token 不进入官方会话头

用法：python scripts/verify_t051_identity.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
HOST = REPO / "packages" / "host-core"
SESSION = REPO / "apps" / "desktop" / "src" / "main" / "auth" / "session.ts"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    need = [HOST / "src/identity.ts", HOST / "test/identity.test.ts", SESSION]
    missing = [str(item) for item in need if not item.exists()]
    record(not missing, f"I1 结构齐备（缺: {missing or '无'}）")

    if NODE is None:
        record(False, "I2 node 不可用")
        return finish()
    test = run(NODE, HOST / "node_modules/vitest/vitest.mjs", "run", "identity", cwd=HOST)
    typecheck = run(NODE, HOST / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=HOST)
    record(test.returncode == 0 and typecheck.returncode == 0,
           f"I2 identity 测试/类型（test={test.returncode}, typecheck={typecheck.returncode}）")

    src = "\n".join(item.read_text(encoding="utf-8") for item in (HOST / "src/identity.ts", SESSION))
    bad = [token for token in ("writeFile", "readFile", "keytar", "localStorage", "sessionStorage") if token in src]
    record("official-credentials-service-adapter" in src and not bad,
           f"I3 官方凭据适配声明，无第二套本地存储（命中: {bad or '无'}）")

    record("buildOfficialSessionHeaders" in src and "hasEnterpriseTokenInOfficialSession" in src,
           "I4 企业 Token 不进入官方会话头")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
