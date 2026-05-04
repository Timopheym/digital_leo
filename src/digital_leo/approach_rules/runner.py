"""Rule-based runner — CLI entrypoint.

Walks the sample manifest, emits:
  - a parallel TEI tree under output/texts/   (round-tripped, unchanged for now;
    wiring annotations into the tree is part of the actual matcher follow-up)
  - per-author bio CSVs under output/bio_csv/  (one row per bio doc, persons
    populated from the stub matcher)
  - a JSON report under output/reports/rules.json
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
from lxml import etree
from rich import print

from ..config import (
    OUTPUT_BIO_CSV,
    OUTPUT_REPORTS,
    OUTPUT_TEI,
    REPO_ROOT,
)
from ..corpus import CorpusFile, iter_sample
from ..io_csv import BioCsvRow, write_bio_csv
from ..io_tei import round_trip
from ..persons import PersonIndex
from ..tracing import init_langfuse_env
from .matcher import Mention, StubMatcher

init_langfuse_env()
from langfuse import get_client, observe  # noqa: E402  — depends on init_langfuse_env

app = typer.Typer(add_completion=False)


def _visible_text(path: Path) -> str:
    tree = etree.parse(str(path))
    return " ".join(tree.getroot().itertext())


@observe(name="rules.process_text", as_type="span")
def _process_text_file(cf: CorpusFile, matcher: StubMatcher) -> dict:
    out_path = round_trip(cf.path, OUTPUT_TEI)
    text = _visible_text(cf.path)
    mentions = matcher.find_mentions(text)
    get_client().update_current_span(
        input={"file_rel": str(cf.rel_to_vendor), "section": cf.section, "chars": len(text)},
        output={"mentions": [(m.text, m.ref_id) for m in mentions]},
        metadata={"approach": "rules", "kind": "texts", "section": cf.section},
    )
    return {
        "rel": str(cf.rel_to_vendor),
        "out": str(out_path.relative_to(REPO_ROOT)),
        "mention_count": len(mentions),
    }


@observe(name="rules.process_bio", as_type="span")
def _process_bio_file(cf: CorpusFile, matcher: StubMatcher) -> tuple[dict, BioCsvRow]:
    text = _visible_text(cf.path)
    mentions = matcher.find_mentions(text)
    person_ids = sorted({m.ref_id for m in mentions})
    row = BioCsvRow(
        uid=cf.stem,
        bibid=cf.section,
        persons=person_ids,
        bibtext=str(cf.rel_to_vendor),
    )
    get_client().update_current_span(
        input={"file_rel": str(cf.rel_to_vendor), "section": cf.section, "chars": len(text)},
        output={"person_ids": person_ids},
        metadata={"approach": "rules", "kind": "bio", "section": cf.section},
    )
    return (
        {
            "rel": str(cf.rel_to_vendor),
            "section": cf.section,
            "person_count": len(person_ids),
        },
        row,
    )


@app.command()
def run(
    in_: str = typer.Option("data/sample", "--in", help="ignored — uses manifest"),
    out: str = typer.Option("output", "--out", help="ignored — fixed in config"),
    limit: int = typer.Option(0, "--limit", help="0 = no limit"),
) -> None:
    print(f"[bold]rules runner[/bold]  in={in_}  out={out}")
    idx = PersonIndex.load()
    print(f"loaded {len(idx)} persons")
    matcher = StubMatcher(idx)

    text_reports: list[dict] = []
    bio_reports: list[dict] = []
    bio_rows_by_section: dict[str, list[BioCsvRow]] = {}

    n = 0
    for cf in iter_sample():
        if limit and n >= limit:
            break
        if cf.kind == "texts":
            text_reports.append(_process_text_file(cf, matcher))
        else:
            rep, row = _process_bio_file(cf, matcher)
            bio_reports.append(rep)
            bio_rows_by_section.setdefault(cf.section, []).append(row)
        n += 1

    for section, rows in bio_rows_by_section.items():
        write_bio_csv(rows, OUTPUT_BIO_CSV / f"{section}.csv")

    OUTPUT_REPORTS.mkdir(parents=True, exist_ok=True)
    report = {
        "approach": "rules",
        "files_processed": n,
        "text_files": text_reports,
        "bio_files": bio_reports,
    }
    (OUTPUT_REPORTS / "rules.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"processed {n} files; report → output/reports/rules.json")
    get_client().flush()


if __name__ == "__main__":
    app()
