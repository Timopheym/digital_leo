"""LLM-based runner — CLI entrypoint with the same I/O shape as the rules runner.

Stub: sends the text and a small candidate slate to OpenAI, parses JSON. No
attempt yet at chunking, smart candidate retrieval, or writing back into TEI.
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
from lxml import etree
from rich import print

from ..config import OUTPUT_BIO_CSV, OUTPUT_REPORTS, OUTPUT_TEI, REPO_ROOT
from ..corpus import CorpusFile, iter_sample
from ..io_csv import BioCsvRow, write_bio_csv
from ..io_tei import round_trip
from ..persons import PersonIndex
from ..tracing import init_langfuse_env
from .client import OpenAiClient
from .prompts import SYSTEM_RU, user_prompt

init_langfuse_env()
from langfuse import get_client, observe  # noqa: E402  — depends on init_langfuse_env

app = typer.Typer(add_completion=False)

CANDIDATE_BUDGET = 30  # how many dictionary entries to put into the prompt
MAX_TEXT_CHARS = 4000  # truncate long files for the stub


def _visible_text(path: Path) -> str:
    tree = etree.parse(str(path))
    return " ".join(tree.getroot().itertext())


def _shortlist(idx: PersonIndex, text: str, budget: int) -> list[dict]:
    """Cheap shortlist: any dictionary entry whose surname appears in the text."""
    lc = text.lower()
    seen: set[str] = set()
    out: list[dict] = []
    for p in idx:
        if not p.surname:
            continue
        if p.surname.lower() in lc and p.id not in seen:
            seen.add(p.id)
            out.append({"id": p.id, "main_name": p.main_name})
            if len(out) >= budget:
                break
    return out


@observe(name="llm.call", as_type="span")
def _call_llm(client: OpenAiClient, idx: PersonIndex, text: str) -> list[dict]:
    text = text[:MAX_TEXT_CHARS]
    candidates = _shortlist(idx, text, CANDIDATE_BUDGET)
    if not candidates:
        get_client().update_current_span(
            output={"mentions": [], "skipped": "no_candidates"},
            metadata={"candidate_count": 0, "text_chars": len(text)},
        )
        return []
    parsed, _call = client.chat_json(SYSTEM_RU, user_prompt(text, candidates))
    if isinstance(parsed, dict) and "mentions" in parsed:
        mentions = parsed["mentions"]
    elif isinstance(parsed, list):
        mentions = parsed
    else:
        mentions = []
    get_client().update_current_span(
        output={"mentions": mentions},
        metadata={"candidate_count": len(candidates), "text_chars": len(text)},
    )
    return mentions


@observe(name="llm.process_file", as_type="span")
def _process_file(
    cf: CorpusFile,
    client: OpenAiClient,
    idx: PersonIndex,
) -> tuple[str, list[dict]]:
    """Run the LLM on a single corpus file and return (visible_text, mentions)."""
    text = _visible_text(cf.path)
    mentions = _call_llm(client, idx, text)
    get_client().update_current_span(
        input={"file_rel": str(cf.rel_to_vendor), "section": cf.section, "chars": len(text)},
        output={"mention_count": len(mentions)},
        metadata={"approach": "llm", "kind": cf.kind, "section": cf.section, "model": client.model},
    )
    return text, mentions


@app.command()
def run(
    in_: str = typer.Option("data/sample", "--in", help="ignored — uses manifest"),
    out: str = typer.Option("output", "--out", help="ignored — fixed in config"),
    limit: int = typer.Option(2, "--limit", help="0 = no limit; default low to limit cost"),
) -> None:
    print(f"[bold]llm runner[/bold]  in={in_}  out={out}  limit={limit}")
    idx = PersonIndex.load()
    print(f"loaded {len(idx)} persons")
    client = OpenAiClient()
    print(f"using model: {client.model}")

    text_reports: list[dict] = []
    bio_reports: list[dict] = []
    bio_rows_by_section: dict[str, list[BioCsvRow]] = {}

    n = 0
    for cf in iter_sample():
        if limit and n >= limit:
            break
        text, mentions = _process_file(cf, client, idx)
        if cf.kind == "texts":
            out_path = round_trip(cf.path, OUTPUT_TEI)
            text_reports.append(
                {
                    "rel": str(cf.rel_to_vendor),
                    "out": str(out_path.relative_to(REPO_ROOT)),
                    "mention_count": len(mentions),
                }
            )
        else:
            person_ids = sorted({str(m.get("ref_id")) for m in mentions if m.get("ref_id")})
            row = BioCsvRow(
                uid=cf.stem,
                bibid=cf.section,
                persons=person_ids,
                bibtext=str(cf.rel_to_vendor),
            )
            bio_reports.append(
                {"rel": str(cf.rel_to_vendor), "section": cf.section, "person_count": len(person_ids)}
            )
            bio_rows_by_section.setdefault(cf.section, []).append(row)
        n += 1

    for section, rows in bio_rows_by_section.items():
        write_bio_csv(rows, OUTPUT_BIO_CSV / f"{section}.llm.csv")

    OUTPUT_REPORTS.mkdir(parents=True, exist_ok=True)
    report = {
        "approach": "llm",
        "model": client.model,
        "files_processed": n,
        "text_files": text_reports,
        "bio_files": bio_reports,
    }
    (OUTPUT_REPORTS / "llm.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"processed {n} files; report → output/reports/llm.json")
    get_client().flush()


if __name__ == "__main__":
    app()
