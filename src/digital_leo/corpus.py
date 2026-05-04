"""Iterate TEI files in the corpus."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .config import SAMPLE_MANIFEST, TEXTS_DIR, TOLSTOY_BIO_DIR, VENDOR_TEI


@dataclass
class CorpusFile:
    path: Path
    kind: str  # "texts" | "bio"
    section: str  # e.g. "letters", "diaries", "goldenweiser"
    rel_to_vendor: Path

    @property
    def stem(self) -> str:
        return self.path.stem


def _iter_xml(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    yield from sorted(root.rglob("*.xml"))


def iter_texts() -> Iterator[CorpusFile]:
    for p in _iter_xml(TEXTS_DIR):
        rel = p.relative_to(VENDOR_TEI)
        section = rel.parts[1] if len(rel.parts) > 1 else ""
        yield CorpusFile(path=p, kind="texts", section=section, rel_to_vendor=rel)


def iter_bio() -> Iterator[CorpusFile]:
    for p in _iter_xml(TOLSTOY_BIO_DIR):
        rel = p.relative_to(VENDOR_TEI)
        # tolstoy-bio/<author>/data/xml/<file>.xml
        section = rel.parts[1] if len(rel.parts) > 1 else ""
        yield CorpusFile(path=p, kind="bio", section=section, rel_to_vendor=rel)


def iter_all() -> Iterator[CorpusFile]:
    yield from iter_texts()
    yield from iter_bio()


def iter_sample() -> Iterator[CorpusFile]:
    """Yield only files listed in data/sample/manifest.json."""
    if not SAMPLE_MANIFEST.exists():
        raise FileNotFoundError(
            f"Sample manifest not found at {SAMPLE_MANIFEST}. "
            f"Run scripts/build_sample.py first."
        )
    manifest = json.loads(SAMPLE_MANIFEST.read_text())
    for entry in manifest["files"]:
        rel = Path(entry["rel_to_vendor"])
        path = VENDOR_TEI / rel
        yield CorpusFile(
            path=path,
            kind=entry["kind"],
            section=entry["section"],
            rel_to_vendor=rel,
        )
