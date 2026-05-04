"""Pick a curated dev subset from vendor/TEI and write data/sample/manifest.json.

Strategy: deterministic sampling — first/last/middle slices, no RNG, so reruns
are stable. Tweak SAMPLE_PLAN to change what gets included.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as a plain script from repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from digital_leo.config import (  # noqa: E402
    BIBLLIST_BIO,
    PERSON_LIST,
    SAMPLE_DIR,
    SAMPLE_MANIFEST,
    TEXTS_DIR,
    TOLSTOY_BIO_DIR,
    VENDOR_TEI,
)
from digital_leo.gold import BibllistBioIndex  # noqa: E402


SAMPLE_PLAN: dict[str, dict[str, int]] = {
    # texts_section -> count
    # Sections chosen because they actually carry <name type="person"> markup
    # (letters ~8k files, diaries ~2.7k, works ~450, azbuka ~16). texts/comments
    # has 0 person markup and was dropped.
    "texts": {
        "letters": 30,
        "diaries": 20,
        "works": 10,
        "azbuka": 5,
    },
    # bio_author -> count
    "bio": {
        "goldenweiser": 8,
        "gusev": 8,
        "makovitski": 8,
        "tolstaya_diaries": 8,
    },
}


def _evenly_spaced(items: list[Path], n: int) -> list[Path]:
    if not items:
        return []
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def _collect(root: Path, count: int) -> list[Path]:
    files = sorted(root.rglob("*.xml")) if root.exists() else []
    return _evenly_spaced(files, count)


def build() -> dict:
    if not VENDOR_TEI.exists():
        raise FileNotFoundError(
            f"vendor/TEI not found at {VENDOR_TEI}. Run scripts/bootstrap.sh."
        )

    files: list[dict] = []

    for section, count in SAMPLE_PLAN["texts"].items():
        for p in _collect(TEXTS_DIR / section, count):
            files.append(
                {
                    "kind": "texts",
                    "section": section,
                    "rel_to_vendor": str(p.relative_to(VENDOR_TEI)),
                }
            )

    # For bio we sample only files whose xml:id appears in bibllist_bio.xml
    # with at least one non-EMPTY <relation type="person">. Otherwise the
    # gold is structurally empty (most bio xml:ids have ref="EMPTY").
    bibllist = BibllistBioIndex.load() if BIBLLIST_BIO.exists() else BibllistBioIndex()
    labelled_ids = {k for k, v in bibllist.by_xml_id.items() if v}

    for author, count in SAMPLE_PLAN["bio"].items():
        author_root = TOLSTOY_BIO_DIR / author
        candidates: list[Path] = []
        for sub in ("data/xml", "data/tei", "data"):
            d = author_root / sub
            if d.exists():
                candidates = sorted(d.rglob("*.xml"))
                if candidates:
                    break
        if not candidates and author_root.exists():
            candidates = sorted(author_root.rglob("*.xml"))
        labelled = [p for p in candidates if p.stem in labelled_ids]
        chosen = _evenly_spaced(labelled, count) if labelled else []
        for p in chosen:
            files.append(
                {
                    "kind": "bio",
                    "section": author,
                    "rel_to_vendor": str(p.relative_to(VENDOR_TEI)),
                }
            )

    manifest = {
        "person_list": str(PERSON_LIST.relative_to(VENDOR_TEI)),
        "files": files,
    }
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def main() -> None:
    manifest = build()
    n = len(manifest["files"])
    print(f"wrote {SAMPLE_MANIFEST} with {n} files")
    by_kind: dict[str, int] = {}
    for f in manifest["files"]:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
    for k, v in by_kind.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
