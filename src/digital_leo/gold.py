"""Gold dataset extraction from existing TEI markup.

Two flavours of gold:

1. **Texts gold** (per mention): every `<name type="person" ref=...>` and
   `<persName ref=...>` span in `texts/<section>/<file>.xml`, with surface
   form, ID, source line, and placement.

2. **Bio gold** (per document): for each `tolstoy-bio/.../<file>.xml`, the
   set of person IDs declared on its `<relatedItem>` block in
   `reference/bibllist_bio.xml`, looked up by `xml:id == file.stem`.

Both flavours share a deterministic dev/test split derived from a SHA-256
hash of the file path, so the split is stable across reruns.

Caveat — partial gold: the corpus markup itself is partial (high-weight
mentions only, per spec §5). Recall numbers therefore measure agreement with
existing markup, not absolute recall against an exhaustive truth.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from lxml import etree

from .config import (
    BIBLLIST_BIO,
    GOLD_DIR,
    PERSON_LIST,
    TEI_NS,
    VENDOR_TEI,
    XML_NS,
)
from .corpus import CorpusFile
from .existing_markup import find_person_mentions
from .persons import PersonIndex


# ---- Data classes -----------------------------------------------------------


@dataclass(frozen=True)
class GoldTextMention:
    file_rel: str
    section: str
    ref: str
    surface: str
    placement: str | None
    sourceline: int | None
    split: str  # "dev" | "test"

    def as_pair(self) -> tuple[str, str]:
        """Form used by eval.score_mentions: (surface, ref)."""
        return (self.surface, self.ref)


@dataclass
class GoldBioDoc:
    file_rel: str
    section: str
    xml_id: str
    person_refs: list[str]
    found_in_bibllist: bool
    split: str  # "dev" | "test"

    def to_json(self) -> dict:
        return asdict(self)


# ---- Bibllist index ---------------------------------------------------------


@dataclass
class BibllistBioIndex:
    """Map xml:id of a `<relatedItem>` to its set of person refs."""

    by_xml_id: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "BibllistBioIndex":
        path = path or BIBLLIST_BIO
        if not path.exists():
            raise FileNotFoundError(
                f"bibllist_bio.xml not found at {path}. "
                f"Run scripts/bootstrap.sh."
            )
        tree = etree.parse(str(path))
        root = tree.getroot()
        out: dict[str, list[str]] = {}
        for item in root.iter(f"{{{TEI_NS}}}relatedItem"):
            ref_el = item.find(f"{{{TEI_NS}}}ref")
            if ref_el is None:
                continue
            xml_id = ref_el.get(f"{{{XML_NS}}}id") or ref_el.get("id")
            if not xml_id:
                continue
            refs: list[str] = []
            for rel in item.iter(f"{{{TEI_NS}}}relation"):
                if rel.get("type") != "person":
                    continue
                r = rel.get("ref")
                if not r or r == "EMPTY":
                    continue
                refs.append(r)
            # Stable, sorted, deduped.
            out[xml_id] = sorted(set(refs), key=lambda s: (len(s), s))
        return cls(by_xml_id=out)

    def __len__(self) -> int:
        return len(self.by_xml_id)

    def lookup(self, xml_id: str) -> list[str] | None:
        return self.by_xml_id.get(xml_id)


# ---- Split ------------------------------------------------------------------


def split_for(file_rel: str | Path, *, test_ratio: float = 0.2) -> str:
    """Deterministic dev/test split based on SHA-256 of the relative path."""
    s = str(file_rel)
    h = hashlib.sha256(s.encode("utf-8")).digest()
    bucket = int.from_bytes(h[:4], "big") / 0xFFFFFFFF
    return "test" if bucket < test_ratio else "dev"


# ---- Extraction -------------------------------------------------------------


def extract_text_gold(file: CorpusFile) -> list[GoldTextMention]:
    mentions = find_person_mentions(file.path)
    rel = str(file.rel_to_vendor)
    split = split_for(rel)
    out: list[GoldTextMention] = []
    for m in mentions:
        if not m.text:
            continue  # empty surface form: not useful for eval
        out.append(
            GoldTextMention(
                file_rel=rel,
                section=file.section,
                ref=m.ref,
                surface=m.text,
                placement=m.placement,
                sourceline=m.sourceline,
                split=split,
            )
        )
    return out


def extract_bio_gold(file: CorpusFile, bibllist: BibllistBioIndex) -> GoldBioDoc:
    rel = str(file.rel_to_vendor)
    xml_id = file.path.stem
    refs = bibllist.lookup(xml_id) or []
    return GoldBioDoc(
        file_rel=rel,
        section=file.section,
        xml_id=xml_id,
        person_refs=refs,
        found_in_bibllist=bibllist.lookup(xml_id) is not None,
        split=split_for(rel),
    )


# ---- Validation -------------------------------------------------------------


def collect_orphans(
    refs: Iterable[str], person_index: PersonIndex
) -> list[str]:
    """Return refs absent from personList.xml, deduped & sorted."""
    seen: set[str] = set()
    for r in refs:
        if not r:
            continue
        if person_index.by_id(r) is None:
            seen.add(r)
    return sorted(seen, key=lambda s: (len(s), s))


# ---- I/O --------------------------------------------------------------------


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")
            n += 1
    return n


def load_text_gold(path: Path) -> list[GoldTextMention]:
    out: list[GoldTextMention] = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out.append(GoldTextMention(**d))
    return out


def load_bio_gold(path: Path) -> list[GoldBioDoc]:
    out: list[GoldBioDoc] = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out.append(GoldBioDoc(**d))
    return out


# ---- Default paths ----------------------------------------------------------

GOLD_TEXTS_JSONL = GOLD_DIR / "texts.jsonl"
GOLD_BIO_JSONL = GOLD_DIR / "bio.jsonl"
GOLD_STATS_JSON = GOLD_DIR / "stats.json"
GOLD_ORPHANS_TXT = GOLD_DIR / "orphans.txt"
