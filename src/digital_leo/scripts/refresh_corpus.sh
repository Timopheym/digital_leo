#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/vendor/TEI"
git pull --ff-only
git rev-parse HEAD > ../TEI.sha
echo "updated to $(cat ../TEI.sha)"
