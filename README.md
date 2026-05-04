# digital_leo

Person Named-Entity Recognition (NER) and disambiguation over the
[**tolstoydigital/TEI**](https://github.com/tolstoydigital/TEI) corpus —
Leo Tolstoy's complete works, diaries, letters, and surrounding biographical
documents, marked up in TEI XML.

The project compares two interchangeable approaches against the same gold
dataset and the same evaluation harness, so we can measure how far classical
rules go before reaching for an LLM:

| Approach | What it is |
|---|---|
| `digital_leo.approach_rules` | Dictionary + heuristics over `personList.xml` (3,112 persons). No LLM. |
| `digital_leo.approach_llm`   | Surname-shortlist + OpenAI-backed disambiguator with a Russian system prompt. |

Both read TEI from `vendor/TEI/` (cloned locally, not committed), never modify
the corpus, and emit annotated copies to `output/texts/` plus per-author bio
CSVs to `output/bio_csv/` — the same shape consumed by the corpus's own
`utils/import_csv_database_dump_to_bibllist_bio.py`.

---

## What's in here

```
src/digital_leo/
  persons.py            PersonIndex — loads personList.xml (3,112 entries)
  corpus.py             Sample iterator over the manifested TEI files
  io_tei.py             Round-trip TEI reader/writer (preserves namespaces)
  io_csv.py             bibllist_bio-compatible CSV writer
  existing_markup.py    Reads persName / name@type="person" already in the corpus
  gold.py               Gold-set loader (texts + bio splits)
  eval.py               Strict (surface, ref) and ref-only F1
  tracing.py            Langfuse environment bootstrap
  config.py             Repo / vendor / output paths

  approach_rules/
    matcher.py          StubMatcher — variant generation, morphology, disambiguation
    runner.py           CLI: walk sample → emit annotated TEI + CSVs + report

  approach_llm/
    client.py           Langfuse-instrumented OpenAI wrapper (chat_json)
    prompts.py          Russian system prompt with few-shot disambiguation example
    runner.py           CLI: same I/O as rules, with LLM in the middle

  scripts/
    bootstrap.sh        Clone vendor TEI, build venv, install deps, run pytest
    refresh_corpus.sh   Refresh vendor TEI to the pinned SHA
    build_sample.py     Stratified sample manifest across letters/diaries/works/azbuka + bio
    build_gold.py       Extract gold (surface, ref) pairs from existing markup
    upload_dataset.py   Push gold dev split to Langfuse as two datasets
    run_experiment.py   Langfuse experiment runner (rules | llm × texts | bio)
    diff_output.sh      Diff output/ TEI tree against vendor/

data/
  sample/manifest.json  Curated sample (89 files: 65 texts + 24 bio docs)
  gold/                 Frozen gold set built from existing TEI markup
    texts.jsonl         362 mentions across 53 files (162 unique persons)
    bio.jsonl           65 person-relation rows across 24 bio docs (31 unique)
    stats.json          Counts, top refs, splits, orphans
    orphans.txt         76 refs in gold that aren't in personList.xml
    README.md           Schema + caveats

tests/                  pytest suite for io_tei, persons, gold, existing_markup
web/
  persons.html          Single-file HTML/JS browser for personList.xml (3,112 records)
  bibllist_bio.html     Single-file viewer for bibllist_bio.xml with cross-page navigation

vendor/                 (gitignored) — clone of tolstoydigital/TEI, ~5.3 GB
output/                 (gitignored) — annotated TEI, bio CSVs, run reports
```

---

## Setup

```bash
./src/digital_leo/scripts/bootstrap.sh
```

This will:

1. Verify `git`, `python>=3.11`, and `uv`.
2. Shallow-clone the TEI corpus into `vendor/TEI/` and pin its SHA in
   `vendor/TEI.sha`.
3. Create a venv and `uv sync` dependencies.
4. Build the curated sample into `data/sample/manifest.json`.
5. Run `pytest -q`.

For the LLM approach and Langfuse tracing, copy `.env.example` to `.env` and
fill in:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

---

## Run

```bash
# Rule-based — annotate sample, emit TEI + bio CSVs + JSON report
uv run python -m digital_leo.approach_rules.runner --in data/sample --out output

# LLM — same I/O contract; --limit caps files for cost control
uv run python -m digital_leo.approach_llm.runner --in data/sample --out output --limit 2

# Diff output against the vendored corpus
./src/digital_leo/scripts/diff_output.sh | head
```

Both runners are instrumented with Langfuse `@observe()` decorators, so each
file produces a hierarchical trace with per-mention spans visible in the UI.

---

## Evaluation

The gold set is extracted from the corpus's own existing TEI markup
(`<name type="person" ref="…">` and `<persName ref="…">`), then split
deterministically by SHA-256 hash of the file path (~80 / 20 dev / test).

### The dataset

| | files | items | unique refs |
|---|---:|---:|---:|
| **texts** (letters / diaries / works) | 53 / 65 | 362 mentions | 162 |
| **bio**   (gusev / makovitski / tolstaya_diaries) | 24 / 24 | 65 person-relations | 31 |

Splits: `texts/dev` 295 · `texts/test` 67 · `bio/dev` 21 · `bio/test` 3.

### Metrics

For every dataset item the experiment runner computes:

- **`f1`** — strict bag F1 on `(normalized surface, ref)` pairs. Surface is
  case-, punctuation-, whitespace-, and ё/е-normalized so we don't penalise
  trivial differences when the ref is right.
- **`f1_refs`** — relaxed bag F1 on refs only, ignoring surface form. This is
  the headline metric: it tells us whether we found the right *person*,
  regardless of which surface form the system picked.
- `precision`, `recall` — supporting metrics, same bag semantics.
- `mean_f1`, `mean_f1_refs` — run-level aggregates.

### Running an experiment

```bash
# Upload gold dev split to Langfuse as two datasets
uv run python -m digital_leo.scripts.upload_dataset

# Run an experiment
uv run python -m digital_leo.scripts.run_experiment \
  --approach rules --dataset tolstoy-ner-texts

uv run python -m digital_leo.scripts.run_experiment \
  --approach llm   --dataset tolstoy-ner-texts --max-concurrency 4
```

Each run shows up under **Datasets → tolstoy-ner-texts → Runs** in the
Langfuse UI, with traces linked to dataset items and per-item scores attached.

### Latest results — `tolstoy-ner-texts` (40 items)

| Approach | Run | f1 (strict) | f1_refs (headline) |
|---|---|---:|---:|
| Rules | `rules-texts-v5` | 0.067 | 0.151 |
| LLM   | `llm-texts-v4`   | **0.164** | **0.279** |

The LLM beats rules by **~2×** on the headline metric, with most of the
remaining gap explained by:

- **Partial gold**: the corpus markup itself is not exhaustive — only
  "high-weight" mentions are tagged ([Tolstoy_Digital.md §5](Tolstoy_Digital.md)).
  Many true-positive predictions are scored as false positives because gold
  doesn't cover them.
- **Span granularity**: rules predict surname-only surfaces ("Тургенева"),
  while gold often annotates the full multi-word span ("Иван Сергеевич
  Тургенев"). `f1_refs` mostly absorbs this; strict `f1` does not.
- **Orphan refs**: 76 of the gold refs don't exist in `personList.xml` and
  are therefore unmatchable by either approach.

---

## How we got to non-zero

The first experiments scored **F1 = 0** across the board. Five compounding
bugs were responsible; they are all fixed in the current `main`. The
investigation arc, kept here as a useful log:

1. **TEI header contamination** — `_visible_text()` was concatenating the
   `<teiHeader>` (which contains the document author's full name), so every
   text "matched" Tolstoy as the most-frequent person. Fix: scope text
   extraction to `<body>`.
2. **Surface case mismatch** — predictions came back lowercased, gold
   preserved original casing. Strict `(surface, ref)` F1 was 0 even when the
   ref was right. Fix: matcher returns the original surface; evaluator
   normalises both sides (ё/е, punctuation, whitespace).
3. **LLM input truncation + candidate-list bias** — the LLM saw only the
   first 1k chars and the first 30 alphabetically-sorted persons, so target
   persons (Толстой, Тургенев, Руссо) never reached the prompt. Fix: 12k-char
   window, surname-shortlist scan over all 3,112 persons, group-aware
   60-candidate cap, born/died fields in the candidate list.
4. **JSON shape mismatch** — LLM returned `{"mentions":[…]}`, runner expected
   a bare list. Fix: tolerant parser that accepts list / dict / wrapped
   forms and shapes output by `kind` (texts vs. bio).
5. **Rules disambiguation** — for "Лев Толстой" the matcher picked the wrong
   homonym because candidate tokens included surname duplicates and dotted
   initials weren't word-bounded. Fix: patronym-aware name component
   extraction (`_name_components`), variant generation now covers
   "Forename Patronym Surname", regex word-boundary fix for `И. С.`, and
   forename-as-surname false positives ("надежда") gated by patronym-suffix
   detection.

After all five fixes: rules `f1_refs = 0.151`, LLM `f1_refs = 0.279`. First
non-zero baseline.

---

## Web tools

Two single-file HTML viewers (vanilla JS, no build) for browsing the corpus's
reference data directly from the local TEI:

- **`web/persons.html`** — search & browse all 3,112 persons in
  `personList.xml`, with image thumbnails (2,568 / 3,112 have URLs), notes,
  and Wikidata links.
- **`web/bibllist_bio.html`** — viewer for `bibllist_bio.xml` (32k items),
  cross-linked with `personList.xml` so person refs resolve to person pages
  and back. Loads from `file://` or any static server.

Open them in a browser; both fall back to drag-and-drop if the local files
aren't reachable via `fetch()`.

---

## Stack

- **Python ≥ 3.11** with `uv` for the venv and lockfile.
- **lxml** for TEI parsing, **pandas** for CSV, **typer + rich** for CLIs.
- **OpenAI SDK** (`gpt-5.4-mini` by default) for the LLM approach.
- **Langfuse** for tracing, dataset management, and experiment evaluation
  (project `digital_tolstoy`).
- **pytest** (+ `pytest-xdist`) for the test suite.

See `Tolstoy_Digital.md` for the original task spec (in Russian) and
`AGENTS.md` for project conventions.

## License

Code in this repository is released under your chosen license; the
**tolstoydigital/TEI** corpus referenced in `vendor/` is the property of its
authors and is governed by its own licensing.
