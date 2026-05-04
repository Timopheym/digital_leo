"""Build the gold dataset from the sample manifest.

Walks data/sample/manifest.json. For each "texts" file, extracts every
existing `<name type="person" ref="...">` span into texts.jsonl. For each
"bio" file, looks up its `xml:id` in reference/bibllist_bio.xml and writes
the document's person-ref set into bio.jsonl.

Validates all refs against personList.xml; orphans go to orphans.txt.
Writes a stats summary and a deterministic dev/test split.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from digital_leo.config import (  # noqa: E402
    BIBLLIST_BIO,
    GOLD_DIR,
    PERSON_LIST,
    SAMPLE_MANIFEST,
)
from digital_leo.corpus import iter_sample  # noqa: E402
from digital_leo.gold import (  # noqa: E402
    GOLD_BIO_JSONL,
    GOLD_ORPHANS_TXT,
    GOLD_STATS_JSON,
    GOLD_TEXTS_JSONL,
    BibllistBioIndex,
    collect_orphans,
    extract_bio_gold,
    extract_text_gold,
    write_jsonl,
)
from digital_leo.persons import PersonIndex  # noqa: E402


def main() -> int:
    if not SAMPLE_MANIFEST.exists():
        print(
            f"sample manifest not found: {SAMPLE_MANIFEST}\n"
            f"run: python -m digital_leo.scripts.build_sample",
            file=sys.stderr,
        )
        return 2
    if not PERSON_LIST.exists():
        print(
            f"personList.xml not found: {PERSON_LIST}\n"
            f"run: scripts/bootstrap.sh",
            file=sys.stderr,
        )
        return 2

    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    person_index = PersonIndex.load()
    bibllist = BibllistBioIndex.load() if BIBLLIST_BIO.exists() else BibllistBioIndex()

    text_rows: list[dict] = []
    bio_rows: list[dict] = []
    text_ref_counter: Counter[str] = Counter()
    bio_ref_counter: Counter[str] = Counter()
    text_per_section: defaultdict[str, int] = defaultdict(int)
    bio_per_section: defaultdict[str, int] = defaultdict(int)
    text_files_with_gold = 0
    text_files_total = 0
    bio_files_with_gold = 0
    bio_files_total = 0
    bio_missing_in_bibllist: list[str] = []
    split_counts: defaultdict[str, int] = defaultdict(int)

    for cf in iter_sample():
        if cf.kind == "texts":
            text_files_total += 1
            mentions = extract_text_gold(cf)
            if mentions:
                text_files_with_gold += 1
            for m in mentions:
                text_rows.append(asdict(m))
                text_ref_counter[m.ref] += 1
                text_per_section[m.section] += 1
                split_counts[f"texts/{m.split}"] += 1
        elif cf.kind == "bio":
            bio_files_total += 1
            doc = extract_bio_gold(cf, bibllist)
            if doc.person_refs:
                bio_files_with_gold += 1
            if not doc.found_in_bibllist:
                bio_missing_in_bibllist.append(doc.file_rel)
            for r in doc.person_refs:
                bio_ref_counter[r] += 1
            bio_per_section[doc.section] += 1
            split_counts[f"bio/{doc.split}"] += 1
            bio_rows.append(doc.to_json())

    n_text = write_jsonl(GOLD_TEXTS_JSONL, text_rows)
    n_bio = write_jsonl(GOLD_BIO_JSONL, bio_rows)

    all_refs = list(text_ref_counter) + list(bio_ref_counter)
    orphans = collect_orphans(all_refs, person_index)
    GOLD_ORPHANS_TXT.write_text(
        "# refs present in gold but missing from personList.xml\n"
        + "\n".join(orphans)
        + ("\n" if orphans else ""),
        encoding="utf-8",
    )

    stats = {
        "sample_manifest": str(SAMPLE_MANIFEST.relative_to(REPO_ROOT)),
        "person_list_size": len(person_index),
        "bibllist_bio_size": len(bibllist),
        "texts": {
            "files_total": text_files_total,
            "files_with_gold": text_files_with_gold,
            "mentions_total": n_text,
            "unique_persons": len(text_ref_counter),
            "by_section": dict(text_per_section),
            "top_refs": text_ref_counter.most_common(10),
        },
        "bio": {
            "files_total": bio_files_total,
            "files_with_gold": bio_files_with_gold,
            "person_relation_total": sum(bio_ref_counter.values()),
            "unique_persons": len(bio_ref_counter),
            "missing_in_bibllist": bio_missing_in_bibllist,
            "by_section": dict(bio_per_section),
            "top_refs": bio_ref_counter.most_common(10),
        },
        "splits": dict(split_counts),
        "orphan_refs": orphans,
    }
    GOLD_STATS_JSON.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Console summary.
    print(f"texts: {n_text} mentions across {text_files_with_gold}/{text_files_total} files")
    print(f"  by section: {dict(text_per_section)}")
    print(
        f"bio:   {sum(bio_ref_counter.values())} relations across "
        f"{bio_files_with_gold}/{bio_files_total} files"
    )
    print(f"  by section: {dict(bio_per_section)}")
    print(f"splits:        {dict(split_counts)}")
    print(f"orphan refs:   {len(orphans)} -> {GOLD_ORPHANS_TXT}")
    if bio_missing_in_bibllist:
        print(
            f"bio files missing in bibllist_bio.xml: {len(bio_missing_in_bibllist)} "
            "(see stats.json)"
        )
    print(f"wrote: {GOLD_TEXTS_JSONL}, {GOLD_BIO_JSONL}, {GOLD_STATS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
