"""Detect already-present <name type="person" ref=…> spans in TEI files.

Used to (a) avoid re-annotating, (b) seed the gold set, (c) sanity-check the
parser.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from .config import NS, TEI_NS


@dataclass
class ExistingMention:
    ref: str
    text: str
    placement: str | None
    sourceline: int | None

    def __str__(self) -> str:
        loc = f"L{self.sourceline}" if self.sourceline else "?"
        place = f" placement={self.placement}" if self.placement else ""
        return f"  {loc}{place}  ref={self.ref}  «{self.text}»"


def _normalize(s: str | None) -> str:
    if not s:
        return ""
    return " ".join(s.split()).strip()


def find_person_mentions(path: Path) -> list[ExistingMention]:
    tree = etree.parse(str(path))
    root = tree.getroot()
    out: list[ExistingMention] = []
    # Spec/sample shows <name type="person" ref="..."> in the body.
    for el in root.iter(f"{{{TEI_NS}}}name"):
        if el.get("type") != "person":
            continue
        ref = el.get("ref")
        if not ref:
            continue
        # collect the full visible text inside the element
        text = _normalize("".join(el.itertext()))
        out.append(
            ExistingMention(
                ref=ref,
                text=text,
                placement=el.get("placement"),
                sourceline=el.sourceline,
            )
        )
    # Some files may also use <persName ref="..."> in the body — collect them too.
    for el in root.iter(f"{{{TEI_NS}}}persName"):
        ref = el.get("ref")
        if not ref or ref.startswith("Q"):
            continue  # Q-IDs are dictionary cross-refs, not body markup
        text = _normalize("".join(el.itertext()))
        out.append(
            ExistingMention(
                ref=ref,
                text=text,
                placement=el.get("placement"),
                sourceline=el.sourceline,
            )
        )
    return out


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m digital_leo.existing_markup <file.xml> [...]", file=sys.stderr)
        return 2
    total = 0
    for arg in args:
        path = Path(arg)
        mentions = find_person_mentions(path)
        print(f"{path}: {len(mentions)} person mention(s)")
        for m in mentions:
            print(m)
        total += len(mentions)
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
