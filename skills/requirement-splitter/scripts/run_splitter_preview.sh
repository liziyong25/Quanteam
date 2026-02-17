#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <source-markdown> <prefix> [show-count]" >&2
  exit 2
fi

src="$1"
prefix="$2"
show="${3:-20}"

python3 scripts/requirement_splitter.py \
  --source "$src" \
  --prefix "$prefix" \
  --config docs/12_workflows/requirement_splitter_profiles_v1.yaml \
  --show "$show"
