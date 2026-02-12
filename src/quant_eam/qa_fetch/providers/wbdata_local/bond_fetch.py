"""Deprecated compatibility shim.

Re-exporting from `mysql_fetch`.
This module is scheduled for removal after the migration window.
"""

from __future__ import annotations

from quant_eam.qa_fetch.providers.mysql_fetch.bond_fetch import *  # noqa: F401,F403
