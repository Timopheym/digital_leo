"""Upload the gold dev split to Langfuse as two datasets.

Creates / upserts:
  - tolstoy-ner-texts  (one item per file with all gold mentions)
  - tolstoy-ner-bio    (one item per bio file with the gold person-ref set)

Each item embeds the file's visible text in `input` so the experiment runner
does not need access to vendor TEI when executed via Langfuse infrastructure.

Why use the SDK rather than `langfuse-cli`?
  - langfuse-cli 0.0.9 ships a bundled OpenAPI spec that fails validation on
    every POST/PUT (`"nullable" cannot be used without "type"`), so neither
    `datasets create` nor `dataset-items create` are usable.
  - The CLI also does not expose `--input` / `--expectedOutput` (object body
    fields) for dataset items, so the SDK is the right tool here.
  - We do call the CLI for read-only checks (`datasets list`) before/after.
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import print

from lxml import etree

from ..config import REPO_ROOT, TEI_NS, VENDOR_TEI
from ..gold import (
    GOLD_BIO_JSONL,
    GOLD_TEXTS_JSONL,
    load_bio_gold,
    load_text_gold,
)
from ..tracing import init_langfuse_env


def _visible_text(path: Path) -> str:
    """Extract the body text only.

    Why: `<teiHeader>` contains project credits and titleStmt boilerplate that
    repeats canonical author names (e.g. "Толстой Лев Николаевич") in every
    file. Including header text in the runner input causes the rule-based
    matcher to always emit Tolstoy as a false positive on every diary, and
    poisons the LLM candidate shortlist. Body-only extraction matches what
    the gold pipeline annotates.
    """
    tree = etree.parse(str(path))
    root = tree.getroot()
    body = root.find(f"{{{TEI_NS}}}text")
    if body is None:
        body = root
    return " ".join(body.itertext())

app = typer.Typer(add_completion=False)

DATASET_TEXTS = "tolstoy-ner-texts"
DATASET_BIO = "tolstoy-ner-bio"


def _ensure_dataset(name: str, description: str) -> None:
    init_langfuse_env()
    from langfuse import get_client

    lf = get_client()
    lf.create_dataset(name=name, description=description)
    print(f"[green]ensured dataset[/green] {name}")


def _build_text_items(limit: int) -> list[dict]:
    """One dataset item per text file in dev split, grouped from gold mentions."""
    rows = load_text_gold(GOLD_TEXTS_JSONL)
    by_file: dict[str, dict] = {}
    for r in rows:
        if r.split != "dev":
            continue
        entry = by_file.setdefault(
            r.file_rel,
            {"file_rel": r.file_rel, "section": r.section, "mentions": []},
        )
        entry["mentions"].append({"surface": r.surface, "ref": r.ref})

    items: list[dict] = []
    for rel, payload in by_file.items():
        path = VENDOR_TEI / rel
        try:
            text = _visible_text(path)
        except Exception as e:  # noqa: BLE001
            print(f"[yellow]skip {rel}: {e}[/yellow]")
            continue
        items.append(
            {
                "id": f"texts::{rel}",
                "input": {
                    "kind": "texts",
                    "file_rel": rel,
                    "section": payload["section"],
                    "text": text,
                },
                "expected_output": {"mentions": payload["mentions"]},
                "metadata": {"section": payload["section"], "mention_count": len(payload["mentions"])},
            }
        )
    items.sort(key=lambda x: x["id"])
    return items[:limit] if limit else items


def _build_bio_items(limit: int) -> list[dict]:
    rows = load_bio_gold(GOLD_BIO_JSONL)
    items: list[dict] = []
    for r in rows:
        if r.split != "dev":
            continue
        if not r.person_refs:
            continue
        path = VENDOR_TEI / r.file_rel
        try:
            text = _visible_text(path)
        except Exception as e:  # noqa: BLE001
            print(f"[yellow]skip {r.file_rel}: {e}[/yellow]")
            continue
        items.append(
            {
                "id": f"bio::{r.file_rel}",
                "input": {
                    "kind": "bio",
                    "file_rel": r.file_rel,
                    "section": r.section,
                    "text": text,
                },
                "expected_output": {"person_refs": r.person_refs},
                "metadata": {"section": r.section, "ref_count": len(r.person_refs)},
            }
        )
    items.sort(key=lambda x: x["id"])
    return items[:limit] if limit else items


def _upsert_items(dataset_name: str, items: list[dict]) -> None:
    init_langfuse_env()
    from langfuse import get_client

    lf = get_client()
    for it in items:
        lf.create_dataset_item(
            dataset_name=dataset_name,
            id=it["id"],
            input=it["input"],
            expected_output=it["expected_output"],
            metadata=it["metadata"],
        )
    lf.flush()
    print(f"[green]upserted[/green] {len(items)} items → {dataset_name}")


@app.command()
def main(
    limit_texts: int = typer.Option(10, help="0 = upload all dev text files"),
    limit_bio: int = typer.Option(10, help="0 = upload all dev bio files"),
) -> None:
    _ensure_dataset(DATASET_TEXTS, "Tolstoy Digital — text-corpus person NER (dev split)")
    _ensure_dataset(DATASET_BIO, "Tolstoy Digital — bio-corpus person linking (dev split)")

    text_items = _build_text_items(limit_texts)
    print(f"prepared {len(text_items)} text items")
    _upsert_items(DATASET_TEXTS, text_items)

    bio_items = _build_bio_items(limit_bio)
    print(f"prepared {len(bio_items)} bio items")
    _upsert_items(DATASET_BIO, bio_items)


if __name__ == "__main__":
    app()
