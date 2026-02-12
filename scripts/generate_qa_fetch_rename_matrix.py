#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

def _to_fetch_style_text(markdown: str) -> str:
    # The review matrix now uses fetch_* as canonical proposed names.
    return markdown.replace("qa_fetch_*", "fetch_*")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    if src_root.as_posix() not in sys.path:
        sys.path.insert(0, src_root.as_posix())

    from quant_eam.qa_fetch.policy import apply_user_policy
    from quant_eam.qa_fetch.registry import build_fetch_mappings, render_rename_matrix_markdown

    out_dir = repo_root / "docs" / "05_data_plane"
    archive_dir = out_dir / "archive"
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    rows = apply_user_policy(build_fetch_mappings())
    v2_rows = tuple(r for r in rows if r.status != "drop")
    v3_rows = v2_rows
    v1_path = archive_dir / "_draft_qa_fetch_rename_matrix_v1.md"
    v2_path = archive_dir / "_draft_qa_fetch_rename_matrix_v2.md"
    v3_path = out_dir / "_draft_qa_fetch_rename_matrix_v3.md"

    v1_content = _to_fetch_style_text(render_rename_matrix_markdown(rows)) + "\n"
    v2_content = _to_fetch_style_text(render_rename_matrix_markdown(v2_rows)) + "\n"
    v2_content = v2_content.replace("# QA Fetch Rename Matrix (Draft v1)", "# QA Fetch Rename Matrix (Draft v2)")
    v3_content = _to_fetch_style_text(render_rename_matrix_markdown(v3_rows)) + "\n"
    v3_content = v3_content.replace("# QA Fetch Rename Matrix (Draft v1)", "# QA Fetch Rename Matrix (Draft v3)")

    v1_path.write_text(v1_content, encoding="utf-8")
    v2_path.write_text(v2_content, encoding="utf-8")
    v3_path.write_text(v3_content, encoding="utf-8")
    print(f"wrote {v1_path.as_posix()}")
    print(f"wrote {v2_path.as_posix()}")
    print(f"wrote {v3_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
