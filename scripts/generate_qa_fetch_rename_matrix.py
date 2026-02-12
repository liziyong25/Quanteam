#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

def _to_fetch_style_text(markdown: str) -> str:
    # The review matrix now uses fetch_* as canonical proposed names.
    return markdown.replace("qa_fetch_*", "fetch_*")


def _to_external_source_text(markdown: str) -> str:
    text = markdown
    text = text.replace("| mongo_fetch |", "| fetch |")
    text = text.replace("| mysql_fetch |", "| fetch |")
    text = text.replace("- mongo_fetch functions: `48`", "- external source semantics: `source=fetch`")
    text = text.replace("- mysql_fetch functions: `23`", "- engine split: `mongo=48`, `mysql=23`")
    text = text.replace(
        "- collision rule: `mongo_fetch` keeps canonical `fetch_*`; mysql keeps `wb_fetch_*` alias",
        "- collision rule: Mongo-backed canonical `fetch_*`; MySQL keeps `wb_fetch_*` alias",
    )
    text = text.replace(
        "mongo_fetch priority for fetch_* (collision with mysql_fetch)",
        "mongo priority for fetch_* (collision with mysql)",
    )
    return text


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
    baseline_path = out_dir / "qa_fetch_function_baseline_v1.md"
    legacy_v3_path = out_dir / "_draft_qa_fetch_rename_matrix_v3.md"

    v1_content = _to_fetch_style_text(render_rename_matrix_markdown(rows)) + "\n"
    v2_content = _to_fetch_style_text(render_rename_matrix_markdown(v2_rows)) + "\n"
    v2_content = v2_content.replace("# QA Fetch Rename Matrix (Draft v1)", "# QA Fetch Rename Matrix (Draft v2)")
    baseline_content = _to_fetch_style_text(render_rename_matrix_markdown(v3_rows)) + "\n"
    baseline_content = _to_external_source_text(baseline_content)
    baseline_count = len(v3_rows)
    baseline_content = baseline_content.replace(
        "# QA Fetch Rename Matrix (Draft v1)",
        "# QA Fetch Function Baseline v1",
    )
    baseline_content = baseline_content.replace(
        "This document is auto-generated for review before bulk rename.",
        f"This document is the frozen {baseline_count}-function baseline for runtime and agent integration.",
    )
    legacy_v3_content = "\n".join(
        [
            "# Deprecated",
            "",
            "This path is retained for one migration cycle.",
            "Use `docs/05_data_plane/qa_fetch_function_baseline_v1.md` as the canonical baseline.",
            "",
            baseline_content.strip(),
            "",
        ]
    )

    v1_path.write_text(v1_content, encoding="utf-8")
    v2_path.write_text(v2_content, encoding="utf-8")
    baseline_path.write_text(baseline_content, encoding="utf-8")
    legacy_v3_path.write_text(legacy_v3_content, encoding="utf-8")
    print(f"wrote {v1_path.as_posix()}")
    print(f"wrote {v2_path.as_posix()}")
    print(f"wrote {baseline_path.as_posix()}")
    print(f"wrote {legacy_v3_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
