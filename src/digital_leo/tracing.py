"""Langfuse tracing bootstrap shared by both approaches.

The Langfuse Python SDK reads credentials from environment variables
(`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`). Our `.env`
spells the host as `LANGFUSE_BASE_URL` (matching the langfuse-cli convention),
so we alias it before any SDK import.
"""
from __future__ import annotations

import os

from .config import load_env


def init_langfuse_env() -> None:
    """Load .env and ensure LANGFUSE_HOST is populated for the SDK."""
    load_env()
    if not os.environ.get("LANGFUSE_HOST"):
        base = os.environ.get("LANGFUSE_BASE_URL")
        if base:
            os.environ["LANGFUSE_HOST"] = base
