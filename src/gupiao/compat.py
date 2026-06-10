"""Compatibility helpers for supported Python runtimes."""

from __future__ import annotations

from datetime import timezone, tzinfo

UTC: tzinfo = timezone.utc  # noqa: UP017 - keep Python 3.10 runtime compatibility.
