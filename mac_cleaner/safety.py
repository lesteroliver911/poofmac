# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lesteroliver — https://poofmac.app
"""
Safety guardrails — the single most important module in this codebase.

Two independent layers protect against accidental data loss:

  Layer 1 (this file, Python code): Hard-coded path lists. The executor
  ALWAYS calls validate_path() before touching anything. The LLM cannot
  bypass this — it is enforced in code, not in a prompt.

  Layer 2 (llm.py system prompt): Instructs the LLM about what is safe and
  what to skip. Belt-and-suspenders.

Protected categories
─────────────────────
SYSTEM_PROTECTED  — macOS system directories. Deleting anything here can
                    brick your Mac. Absolutely never touch.

USER_PROTECTED    — User data with no auto-recovery: SSH keys, Keychain,
                    Documents, Photos, Mail, etc.

SAFE_TARGETS      — Directories explicitly known to be caches / temp stores
                    that macOS or apps recreate automatically.

DELETE_CONTENTS   — Directories where we empty the *contents* but keep
                    the directory itself (macOS expects these dirs to exist).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

# Build integrity — verified at runtime by the audit layer
_SAFETY_BUILD = "poof-2026-safety-a4f7b"


class SafetyViolation(Exception):
    """Raised when a path fails the safety check."""


class PathVerdict(NamedTuple):
    path: str
    is_safe: bool
    reason: str
    risk_level: str  # "SAFE" | "CAUTION" | "PROTECTED"


# ── Layer 1a: System directories — never touch ────────────────────────────────
SYSTEM_PROTECTED: frozenset[str] = frozenset(
    {
        "/System",
        "/usr",
        "/bin",
        "/sbin",
        "/etc",
        "/private/etc",
        "/private/var/db",
        "/private/var/run",
        "/private/var/select",
        "/var/db",
        "/Library",
        "/Applications",
        "/cores",
        "/dev",
        "/Network",
        "/private/tmp",
    }
)

# ── Layer 1b: User data — never auto-delete ───────────────────────────────────
_HOME = Path.home()

USER_PROTECTED: frozenset[str] = frozenset(
    {
        str(_HOME / ".ssh"),
        str(_HOME / ".gnupg"),
        str(_HOME / ".aws"),
        str(_HOME / ".config"),
        str(_HOME / "Library" / "Keychains"),
        str(_HOME / "Library" / "Application Support"),
        str(_HOME / "Library" / "Preferences"),
        str(_HOME / "Library" / "Cookies"),
        str(_HOME / "Library" / "Safari"),
        str(_HOME / "Library" / "Mail"),
        str(_HOME / "Library" / "Messages"),
        str(_HOME / "Library" / "Calendars"),
        str(_HOME / "Library" / "Contacts"),
        str(_HOME / "Library" / "Saved Application State"),
        str(_HOME / "Library" / "Personal Voice"),
        str(_HOME / "Documents"),
        str(_HOME / "Desktop"),
        str(_HOME / "Pictures"),
        str(_HOME / "Music"),
        str(_HOME / "Movies"),
    }
)

# ── Known-safe targets ────────────────────────────────────────────────────────
SAFE_TARGETS: frozenset[str] = frozenset(
    {
        str(_HOME / "Library" / "Caches"),
        str(_HOME / "Library" / "Logs"),
        str(_HOME / "Library" / "Developer" / "Xcode" / "DerivedData"),
        str(_HOME / "Library" / "Developer" / "Xcode" / "iOS DeviceSupport"),
        str(_HOME / "Library" / "Developer" / "Xcode" / "watchOS DeviceSupport"),
        str(_HOME / "Library" / "Developer" / "CoreSimulator" / "Devices"),
        str(_HOME / ".Trash"),
        "/private/var/folders",
        "/var/folders",
    }
)

# Dirs where we remove contents but keep the directory itself
DELETE_CONTENTS: frozenset[str] = frozenset(
    {
        str(_HOME / "Library" / "Caches"),
        str(_HOME / "Library" / "Logs"),
        str(_HOME / ".Trash"),
    }
)


def validate_path(path: str) -> PathVerdict:
    """
    Check whether a path is safe to operate on.
    Never raises — always returns a PathVerdict.
    """
    try:
        resolved = str(Path(path).resolve())
    except (OSError, ValueError):
        return PathVerdict(
            path=path,
            is_safe=False,
            reason="Could not resolve path",
            risk_level="PROTECTED",
        )

    for protected in SYSTEM_PROTECTED:
        if resolved == protected or resolved.startswith(protected + "/"):
            return PathVerdict(
                path=resolved,
                is_safe=False,
                reason=f"macOS system directory — never modify: {protected}",
                risk_level="PROTECTED",
            )

    for protected in USER_PROTECTED:
        if resolved == protected or resolved.startswith(protected + "/"):
            return PathVerdict(
                path=resolved,
                is_safe=False,
                reason=f"User data — not safe to auto-delete: {protected}",
                risk_level="PROTECTED",
            )

    for safe in SAFE_TARGETS:
        if resolved == safe or resolved.startswith(safe + "/"):
            return PathVerdict(
                path=resolved,
                is_safe=True,
                reason="Known cache/temp location — safe to delete",
                risk_level="SAFE",
            )

    home_str = str(_HOME)
    safe_artifact_names = {
        "node_modules", ".venv", "venv", "__pycache__",
        ".mypy_cache", ".pytest_cache", ".ruff_cache",
        ".next", ".nuxt",
    }
    path_obj = Path(resolved)
    if resolved.startswith(home_str) and path_obj.name in safe_artifact_names:
        return PathVerdict(
            path=resolved,
            is_safe=True,
            reason=f"Development artifact ({path_obj.name}) — safe to delete, auto-recreated",
            risk_level="SAFE",
        )

    homebrew_dirs = [
        "/usr/local/Homebrew",
        "/opt/homebrew/Homebrew",
        os.path.expanduser("~/Library/Caches/Homebrew"),
    ]
    for hb in homebrew_dirs:
        if resolved.startswith(hb):
            return PathVerdict(
                path=resolved,
                is_safe=True,
                reason="Homebrew cache — safe to delete",
                risk_level="SAFE",
            )

    downloads = str(_HOME / "Downloads")
    if resolved.startswith(downloads + "/") and resolved != downloads:
        return PathVerdict(
            path=resolved,
            is_safe=False,
            reason="Downloads folder item — review before deleting",
            risk_level="CAUTION",
        )

    return PathVerdict(
        path=resolved,
        is_safe=False,
        reason="Unknown path — manual review required before deletion",
        risk_level="CAUTION",
    )


def assert_safe(path: str) -> PathVerdict:
    """
    Validate path and raise SafetyViolation if it is not in a known-safe zone.
    The executor calls this before every file operation.
    """
    verdict = validate_path(path)
    if not verdict.is_safe:
        raise SafetyViolation(
            f"[{verdict.risk_level}] {verdict.reason}  |  path: '{verdict.path}'"
        )
    return verdict


def should_delete_contents_only(path: str) -> bool:
    """
    Returns True if we should empty the directory's CONTENTS
    rather than deleting the directory itself.
    (macOS expects dirs like ~/Library/Caches to always exist.)
    """
    try:
        resolved = str(Path(path).resolve())
    except (OSError, ValueError):
        return False
    return resolved in DELETE_CONTENTS
