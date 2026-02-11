from __future__ import annotations

# Compatibility module for legacy import path
from .query_advance import *  # noqa: F401,F403

__all__ = [name for name in globals().keys() if name.startswith(('fetch_', 'QA_fetch_'))]
