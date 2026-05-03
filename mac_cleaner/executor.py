# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lesteroliver — https://poofmac.app
"""
Safe file executor — the only code that actually deletes files.

Every deletion goes through THREE independent gates:
  1. safety.assert_safe()      — Python code, cannot be bypassed by LLM.
  2. safe_mode / dry_run flags — if either is True, nothing is touched.
  3. audit.log()               — every operation is recorded before execution.

The LLM never calls this directly. Only the TUI calls Executor after the
user has reviewed and approved items in the cleanup plan.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from mac_cleaner.audit import AuditLogger
from mac_cleaner.safety import SafetyViolation, assert_safe, should_delete_contents_only
from mac_cleaner.scanner import format_size


class DeleteResult:
    """Result of a single delete operation."""

    def __init__(
        self,
        path: str,
        action: str,
        size_freed: int = 0,
        error: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        self.path = path
        self.action = action          # deleted | dry_run | safe_mode | blocked | error
        self.size_freed = size_freed
        self.size_freed_human = format_size(size_freed)
        self.error = error
        self.dry_run = dry_run

    @property
    def success(self) -> bool:
        return self.action in ("deleted", "dry_run", "safe_mode")

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "action": self.action,
            "size_freed": self.size_freed,
            "size_freed_human": self.size_freed_human,
            "error": self.error,
            "dry_run": self.dry_run,
        }


class Executor:
    def __init__(self, safe_mode: bool, audit: AuditLogger) -> None:
        self.safe_mode = safe_mode
        self.audit = audit

    # ── Public API ─────────────────────────────────────────────────────────────

    def delete(self, path: str, dry_run: bool = True) -> DeleteResult:
        """
        Delete a file or directory.

        Parameters
        ----------
        path    : Absolute path to delete.
        dry_run : If True (default), calculate and report what WOULD happen
                  without touching the filesystem.

        If safe_mode is set on the Executor, dry_run is always True.
        """
        effective_dry_run = dry_run or self.safe_mode

        # ── Gate 1: Safety check ───────────────────────────────────────────
        try:
            assert_safe(path)
        except SafetyViolation as exc:
            self.audit.log("BLOCKED", path, 0, str(exc))
            return DeleteResult(path=path, action="blocked", error=str(exc))

        # ── Gate 2: Path existence ─────────────────────────────────────────
        target = Path(path)
        if not target.exists():
            return DeleteResult(
                path=path, action="not_found", error=f"Path not found: {path}"
            )

        # ── Measure size ───────────────────────────────────────────────────
        size = self._measure(target)

        # ── Gate 3: Dry-run / safe mode ────────────────────────────────────
        if effective_dry_run:
            action = "safe_mode" if self.safe_mode else "dry_run"
            self.audit.log(action.upper(), path, size, "Would delete (not executed)")
            return DeleteResult(
                path=path, action=action, size_freed=size, dry_run=True
            )

        # ── Execution ──────────────────────────────────────────────────────
        try:
            if should_delete_contents_only(path):
                self._empty_directory(target)
            elif target.is_file() or target.is_symlink():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(str(target))
            else:
                return DeleteResult(
                    path=path, action="error", error="Unknown path type"
                )

            self.audit.log("DELETED", path, size, "User approved deletion via TUI")
            return DeleteResult(path=path, action="deleted", size_freed=size)

        except PermissionError as exc:
            msg = f"Permission denied: {exc}"
            self.audit.log("ERROR", path, 0, msg)
            return DeleteResult(path=path, action="error", error=msg)
        except OSError as exc:
            msg = f"OS error: {exc}"
            self.audit.log("ERROR", path, 0, msg)
            return DeleteResult(path=path, action="error", error=msg)

    def delete_many(
        self, paths: list[str], dry_run: bool = True
    ) -> list[DeleteResult]:
        """Delete multiple paths, returning a result for each."""
        return [self.delete(path, dry_run=dry_run) for path in paths]

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _measure(target: Path) -> int:
        """Estimate size in bytes without subprocess (acceptable accuracy)."""
        if target.is_file():
            try:
                return target.stat().st_size
            except OSError:
                return 0
        if target.is_dir():
            total = 0
            try:
                for dirpath, _, filenames in os.walk(str(target)):
                    for fname in filenames:
                        fp = os.path.join(dirpath, fname)
                        try:
                            total += os.path.getsize(fp)
                        except OSError:
                            pass
            except OSError:
                pass
            return total
        return 0

    @staticmethod
    def _empty_directory(target: Path) -> None:
        """Remove all contents of a directory but keep the directory itself."""
        for item in target.iterdir():
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(str(item))
            else:
                item.unlink(missing_ok=True)
