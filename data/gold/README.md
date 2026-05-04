# Gold dataset

Built from existing markup in `vendor/TEI`, against the file selection in
`data/sample/manifest.json`. Re-build with:

```bash
uv run python -m digital_leo.scripts.build_sample   # if sample changed
uv run python -m digital_leo.scripts.build_gold
```

## Files

| File | Format | Granularity |
|---|---|---|
| `texts.jsonl` | one mention per line | each `<name type="person" ref="ID">` / `<persName ref="ID">` span in `texts/` |
| `bio.jsonl` | one document per line | the document's set of person IDs from `bibllist_bio.xml` |
| `stats.json` | summary | counts, top refs, splits, orphans |
| `orphans.txt` | text list | refs in gold that are absent from `personList.xml` |

### `texts.jsonl` row schema

```json
{
  "file_rel": "texts/letters/v59_063_N_A_Nekrasovu.xml",
  "section": "letters",
  "ref": "9649",
  "surface": "Некрасовъ",
  "placement": "text",
  "sourceline": 47,
  "split": "dev"
}
```

### `bio.jsonl` row schema

```json
{
  "file_rel": "tolstoy-bio/.../makovitski-diaries_1904-10-26_1904-10-26.xml",
  "section": "makovitski",
  "xml_id": "makovitski-diaries_1904-10-26_1904-10-26",
  "person_refs": ["9649", "13883"],
  "found_in_bibllist": true,
  "split": "dev"
}
```

## Splits

`split` is a deterministic SHA-256 hash bucket of `file_rel` (~20% test). The
same file always lands in the same split across reruns.

## Sampling notes

- **Texts**: stratified across `letters`, `diaries`, `works`, `azbuka`. The
  `comments` section is excluded — it carries 0 person markup. `azbuka`
  rarely contributes (only ~16 of 784 files have markup).
- **Bio**: filtered to documents whose `xml:id` appears in
  `reference/bibllist_bio.xml` with at least one non-`EMPTY`
  `<relation type="person">`. Authors with **no** labelled entries
  (`goldenweiser` at the time of writing) are skipped. This is a real
  dataset gap, not a bug — most bio `<relatedItem>` blocks ship with
  `ref="EMPTY"` placeholders.

## Caveats

1. **Partial gold (texts)**. The corpus markup is itself partial — only
   "high-weight" mentions are tagged (per `Tolstoy_Digital.md` §5).
   Recall numbers therefore measure agreement with existing markup, not
   absolute recall against an exhaustive truth.
2. **Sparse gold (bio)**. Most bibllist `<relation type="person">` entries
   are `EMPTY` for surrounding-bio authors; the labelled subset is small
   (~80 of ~18k entries across the four bio authors). This is what the
   project aims to fix; treat the gold here as a smoke set, not a benchmark.
3. **Orphan refs**. 76 refs in the gold are not present in
   `personList.xml`. See `orphans.txt`. Reasons may include schema-version
   drift, deleted persons, or numeric-ID collisions; the import pipeline
   should surface these.

## How to evaluate against gold

```python
from digital_leo.eval import score_mentions
from digital_leo.gold import load_text_gold, GOLD_TEXTS_JSONL

gold = load_text_gold(GOLD_TEXTS_JSONL)
gold_pairs = [(g.surface, g.ref) for g in gold if g.split == "dev"]

pred_pairs = ...   # whatever your runner emits, as (surface, ref)
score = score_mentions(gold_pairs, pred_pairs)
print(score.as_dict())
```
