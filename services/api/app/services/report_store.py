"""诊断报告存储：默认 30 天、上限 180 天，只保存白名单化报告。"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class ReportStore:
    def __init__(self, path: Path | None = None):
        self._path = path
        self._reports: list[dict[str, Any]] = []
        self.settings = {"enabled": False, "retentionDays": 30, "noticeShown": False}
        if path is not None and path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._reports.append(json.loads(line))

    def set_settings(self, enabled: bool, retention_days: int) -> dict[str, Any]:
        self.settings["enabled"] = enabled
        self.settings["retentionDays"] = min(max(retention_days, 1), 180)
        self.settings["noticeShown"] = self.settings.get("noticeShown", False)
        return self.get_settings()

    def get_settings(self) -> dict[str, Any]:
        return dict(self.settings)

    def save(self, report: dict[str, Any]) -> dict[str, Any]:
        row = {
            "reportId": str(uuid.uuid4()),
            "receivedAt": time.time(),
            "retainUntil": time.time() + self.settings["retentionDays"] * 86400,
            **report,
        }
        self._reports.append(row)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        return row

    def list(self) -> list[dict[str, Any]]:
        return list(self._reports)

    def cleanup(self) -> int:
        now = time.time()
        keep = [row for row in self._reports if float(row.get("retainUntil", 0)) > now]
        removed = len(self._reports) - len(keep)
        self._reports = keep
        if self._path is not None:
            self._path.write_text(
                "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in keep),
                encoding="utf-8",
            )
        return removed
