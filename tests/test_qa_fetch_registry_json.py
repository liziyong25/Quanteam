from __future__ import annotations

import json
from pathlib import Path


def test_qa_fetch_registry_json_exists_and_has_resolver_entries() -> None:
    path = Path("docs/05_data_plane/qa_fetch_registry_v1.json")
    assert path.is_file()
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc.get("schema_version") == "qa_fetch_registry_v1"
    assert isinstance(doc.get("functions"), list)
    assert isinstance(doc.get("resolver_entries"), list)
    assert len(doc["resolver_entries"]) >= 10
