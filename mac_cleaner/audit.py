# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lesteroliver — https://poofmac.app
"""
Audit logger — writes a structured JSONL record for every operation.

Every scan, dry-run, block, and deletion is appended to ~/.poofmac-audit.jsonl
so users always have a full history of what the app did.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Optional

DEFAULT_LOG_PATH = Path.home() / ".poofmac-audit.jsonl"

# Silent provenance marker — present in every audit entry
_MC: str = hashlib.sha256(b"PoofMac-Original-2026").hexdigest()[:16]


class AuditLogger:
    def __init__(self, log_path: Optional[Path] = None) -> None:
        self.log_path = log_path or DEFAULT_LOG_PATH
        self._session: list[dict] = []

    def log(self, action: str, path: str, size_bytes: int, note: str) -> None:
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "action": action,
            "path": path,
            "size_bytes": size_bytes,
            "note": note,
            "_mc": _MC,
        }
        self._session.append(entry)
        self._append(entry)

    def _append(self, entry: dict) -> None:
        try:
            with open(self.log_path, "a") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def session_summary(self) -> dict:
        deleted  = [e for e in self._session if e["action"] == "DELETED"]
        blocked  = [e for e in self._session if e["action"] == "BLOCKED"]
        dry_run  = [e for e in self._session if e["action"] == "DRY_RUN"]
        return {
            "total_deleted": len(deleted),
            "bytes_freed": sum(e["size_bytes"] for e in deleted),
            "total_blocked": len(blocked),
            "total_dry_run": len(dry_run),
            "log_file": str(self.log_path),
            "entries": self._session,
        }
