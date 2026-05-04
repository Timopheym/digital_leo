# Task: Person NER & Linking for Tolstoy Digital

## Goal

Build a semi-automatic system that detects, links, validates, and enriches
mentions of persons in the Tolstoy Digital TEI corpus, using `personList.xml`
as the canonical authority.

## Inputs

- **Person dictionary**: `vendor/TEI/reference/personList.xml` — TEI `listPerson`
  with unique IDs, decomposed names (`forename`/`surname`), and name variants.
- **Tolstoy texts & comments**: `vendor/TEI/texts/` (letters, diaries, comments, etc.)
- **Surrounding texts (bio)**: `vendor/TEI/tolstoy-bio/` (Goldenweiser, Gusev,
  Makovitski, Tolstaya diaries/letters).
- **Existing markup**: partial `<name type="person" ref="ID">` tags already
  present for high-weight mentions — must be preserved and validated, not
  overwritten.
- **Auxiliary**: name indexes (volumes/pages where persons appear) used for
  validation and disambiguation.

## Required outputs

### 1. Tolstoy texts & comments (`texts/`)
- Mark **every** mention of a person with TEI markup linked to `personList`
  by ID:
  ```xml
  <name type="person" ref="{id}">…surface form…</name>
  ```
- Repeat-mention strategy: support an attribute (e.g. `rend="hidden"`) so the
  front-end can suppress redundant tooltips without losing the link.

### 2. Surrounding bio texts (`tolstoy-bio/`)
- Do **not** annotate every occurrence in the body.
- Instead, for each document, record the **set** of persons mentioned (≥ 1 time).
- Emit a CSV per author/collection for DB import, then sync into
  `vendor/TEI/reference/bibllist_bio.xml`.

## Functional requirements

### Recognition
- Match by full name, surname, forename, initials + surname, and known variants.
- Handle Russian morphology (declensions) for surface forms in running text.

### Disambiguation
- Resolve homonyms (same surname → multiple IDs) using context: era, milieu,
  co-occurring names, and the document's name index when available.

### Mention weighting
- Score each candidate mention by:
  - string-similarity to dictionary forms,
  - presence in the document's name index (volume/page),
  - context fit.
- Use the score to prioritize human review, drive display rules, and filter noise.

### Validation against existing markup
- Detect **missed** entities (dictionary form present but unmarked).
- Flag **wrong** ID bindings.
- Flag **inconsistent** markup within a document (same entity sometimes
  marked, sometimes not; partial-name marked while full-name unmarked).
- Detect duplicate / conflicting tags.

### Working with existing markup
- Recognize already-tagged mentions, never duplicate them, but allow
  refinement: normalize attributes, fill in missing ones, correct IDs.

### Derived data (bio)
- Auto-generate per-document person lists.
- Export CSV in the schema accepted by
  `vendor/TEI/utils/import_csv_database_dump_to_bibllist_bio.py`
  (semicolon-delimited, Python-literal list columns).

### LLM / agent layer
- Agents propose annotations and `personList` bindings, returning:
  - candidate ID(s),
  - confidence score,
  - short rationale (auditable),
  - flag for ambiguous / low-confidence cases.

## Non-goals (for this iteration)

- No changes to `personList.xml` schema (a new schema is in development upstream).
- No HTML/front rendering — only TEI + CSV outputs.
- No automatic merging of conflicting human-made markup; surface conflicts
  for review instead.

## Acceptance criteria

- Round-trip on unchanged files produces zero diff against `vendor/TEI`.
- For a held-out gold sample, report precision / recall / F1 against existing
  `<name type="person">` markup, separately for rule-based and LLM approaches.
- Bio CSVs reimport cleanly via the upstream importer with no schema errors.
- A validation report lists missed / wrong / inconsistent / duplicate cases
  with file + line references.

## Reference

Source spec (Russian): [`../Tolstoy_Digital.md`](../Tolstoy_Digital.md)
