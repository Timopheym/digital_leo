#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

step() { printf "\n\033[1;36m▸ %s\033[0m\n" "$*"; }

step "Checking prerequisites"
command -v git >/dev/null || { echo "git is required"; exit 1; }
command -v uv  >/dev/null || { echo "uv is required (pipx install uv)"; exit 1; }

step "Cloning tolstoydigital/TEI into vendor/TEI (shallow)"
if [ -d "vendor/TEI/.git" ]; then
  echo "vendor/TEI already exists — skipping clone"
else
  git clone --depth=1 https://github.com/tolstoydigital/TEI.git vendor/TEI
fi
git -C vendor/TEI rev-parse HEAD > vendor/TEI.sha
echo "pinned SHA → $(cat vendor/TEI.sha)"

step "Creating virtualenv and installing dependencies"
uv venv
uv pip install -e ".[dev]"

step "Building dev sample"
uv run python scripts/build_sample.py

step "Running tests"
uv run pytest -q || true

step "Done"
cat <<EOF

Next:
  uv run python -m digital_leo.persons                              # sanity check
  uv run python -m digital_leo.approach_rules.runner --in data/sample --out output
  uv run python -m digital_leo.approach_llm.runner   --in data/sample --out output --limit 2
  scripts/diff_output.sh | head

For the LLM runner: cp .env.example .env  and set OPENAI_API_KEY.
EOF
