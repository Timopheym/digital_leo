#!/usr/bin/env bash
# Diff the output tree against the source corpus. Useful to inspect what the
# annotators changed — the parallel-output strategy relies on this.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -d output/tei ]; then
  echo "no output/tei/ — run a runner first"
  exit 1
fi

if command -v diff >/dev/null; then
  diff -ruN vendor/TEI/texts output/tei/texts || true
else
  echo "diff not installed"
  exit 1
fi
