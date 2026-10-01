#!/usr/bin/env python
"""T-064 门禁：引用展示与检索日志（P3-F06 / P3-F08）。

断言：
  N1  结构与迁移齐备
  N2  插件测试与类型检查通过
  N3  控制面 pytest 全量通过
  N4  引用可追溯到标题 / 片段 / 链接，且渲染转义
  N5  检索日志字段齐全（请求摘要、命中数、知识库、用户、空间、耗时）
  N6  隐私边界：日志不保存查询正文与文档正文
  N7  日志只追加（无更新/删除接口）
  N8  PG17 迁移 0004 可升可降

用法：python scripts/verify_t064_citations_logs.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
PLUGIN = REPO / "plugins" / "knowledge"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")
CONTAINER = "worknexus-dsh-postgres"
PG_URL = "postgresql+psycopg://worknexus:worknexus_dev_password@127.0.0.1:15432/worknexus"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600, env=env)


def psql(sql: str) -> str:
    return run("docker", "exec", CONTAINER, "psql", "-U", "worknexus", "-d", "worknexus", "-Atc", sql).stdout.strip()


def main() -> int:
    needed = [
        PLUGIN / "src" / "citations.tsx",
        PLUGIN / "test" / "citations.test.tsx",
        API / "app" / "routers" / "kb_logs.py",
        API / "tests" / "test_kb_logs.py",
        API / "migrations" / "versions" / "0004_knowledge_retrieval_log.py",
    ]
    missing = [path.name for path in needed if not path.exists()]
    record(not missing, f"N1 结构与迁移齐备（缺: {missing or '无'}）")

    if NODE is not None:
        test = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
        typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
        tail = [l.strip() for l in test.stdout.splitlines() if "Tests" in l]
        record(test.returncode == 0 and typecheck.returncode == 0,
               f"N2 插件测试/类型（test={test.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")
    else:
        record(False, "N2 node 不可用")

    pytest = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = pytest.stdout.strip().splitlines()[-1] if pytest.stdout else ""
    record(pytest.returncode == 0, f"N3 控制面 pytest（{tail}）")

    citations = (PLUGIN / "src" / "citations.tsx").read_text(encoding="utf-8")
    citation_test = (PLUGIN / "test" / "citations.test.tsx").read_text(encoding="utf-8")
    record(
        all(token in citations for token in ("documentId", "title", "snippet", "url"))
        and "&lt;script&gt;" in citation_test and "无引用" in citations,
        "N4 引用含标题/片段/链接并可追溯，渲染转义且有空态",
    )

    router = (API / "app" / "routers" / "kb_logs.py").read_text(encoding="utf-8")
    model = (API / "app" / "models" / "kb.py").read_text(encoding="utf-8")
    api_test = (API / "tests" / "test_kb_logs.py").read_text(encoding="utf-8")
    required_fields = ("hit_count", "duration_ms", "knowledge_base_id", "user_id", "space_id", "query_hash", "query_length")
    record(
        all(field in model for field in required_fields)
        and "sha256" in router
        and "hitCount" in api_test and "durationMs" in api_test and "queryHash" in api_test,
        "N5 日志字段齐全（请求摘要/命中数/知识库/用户/空间/耗时）",
    )

    plaintext_hits = [token for token in ("query_text", "query: Mapped", "content: Mapped", "body: Mapped") if token in model]
    record(
        not plaintext_hits and "not in listed.text" in api_test and "not in created.text" in api_test,
        f"N6 不保存查询正文与文档正文（命中: {plaintext_hits or '无'}）",
    )

    write_methods = [token for token in ("@router.patch", "@router.put", "@router.delete") if token in router]
    record(not write_methods, f"N7 日志只追加（命中写方法: {write_methods or '无'}）")

    state = run("docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER).stdout.strip()
    if state != "healthy":
        record(False, f"N8 PG17 容器状态 {state or 'missing'}")
    else:
        env = dict(os.environ, DATABASE_URL=PG_URL)
        up = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        present = psql("select count(*) from information_schema.tables where table_name='knowledge_retrieval_logs'") == "1"
        down = run(PYTHON, "-m", "alembic", "downgrade", "0003", cwd=API, env=env)
        gone = psql("select count(*) from information_schema.tables where table_name='knowledge_retrieval_logs'") == "0"
        back = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        record(up.returncode == 0 and down.returncode == 0 and back.returncode == 0 and present and gone,
               f"N8 PG17 迁移 0004 可升可降（up={up.returncode}, down={down.returncode}, "
               f"head 有表={present}, 降级后无表={gone}）")
        run(PYTHON, "-m", "alembic", "downgrade", "base", cwd=API, env=env)

    stripped = re.sub(r"#.*$", "", router, flags=re.M)
    record("全文" not in stripped or "不保存" in router, "N8b 路由注释声明的隐私边界与实现一致")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
