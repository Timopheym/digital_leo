# digital_leo

Person-NER over the [tolstoydigital/TEI](https://github.com/tolstoydigital/TEI)
corpus. Two interchangeable approaches share the same input/output contract:

- `digital_leo.approach_rules` — dictionary + heuristics, no LLM
- `digital_leo.approach_llm` — OpenAI-backed disambiguator

Both read TEI from `vendor/TEI/`, never modify it, and write annotated copies
to `output/texts/` plus bio CSVs to `output/bio_csv/` (format compatible with
`vendor/TEI/utils/import_csv_database_dump_to_bibllist_bio.py`).

## Setup

```bash
./scripts/bootstrap.sh
```

This will:

1. Check `git`, `python>=3.11`, `uv`.
2. Shallow-clone the TEI corpus into `vendor/TEI/` and pin its SHA in `vendor/TEI.sha`.
3. Create a venv and install dependencies (`uv sync`).
4. Build a curated sample into `data/sample/manifest.json`.
5. Run `pytest -q`.

For the LLM approach, copy `.env.example` to `.env` and set `OPENAI_API_KEY`.

## Run

```bash
# rule-based
uv run python -m digital_leo.approach_rules.runner --in data/sample --out output

# LLM
uv run python -m digital_leo.approach_llm.runner --in data/sample --out output --limit 2

# diff against the original corpus
scripts/diff_output.sh | head
```

## Layout

See `Tolstoy_Digital.md` for the spec; `~/.claude/plans/properly-read-the-tolstoy-digital-md-floofy-falcon.md` for the setup plan.
