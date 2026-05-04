"""We must never overwrite existing <name type="person" ref="..."> markup."""
from __future__ import annotations

from pathlib import Path

import pytest

from digital_leo.config import VENDOR_TEI
from digital_leo.existing_markup import find_person_mentions

KNOWN_LETTER = VENDOR_TEI / "texts" / "letters" / "v59_063_N_A_Nekrasovu.xml"

needs_corpus = pytest.mark.skipif(
    not KNOWN_LETTER.exists(),
    reason="vendor/TEI not cloned; run scripts/bootstrap.sh",
)


@needs_corpus
def test_known_letter_has_three_persons():
    mentions = find_person_mentions(KNOWN_LETTER)
    refs = sorted({m.ref for m in mentions})
    # WebFetch identified refs 9649 (Nekrasov), 13883 (Tolstoy), 13893 (brother).
    for expected in ("9649", "13883", "13893"):
        assert expected in refs, f"expected ref {expected} in {refs}"


def test_synthetic_xml_extracts_refs(tmp_path: Path):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <text><body><p>
    Hello, <name type="person" ref="42">Ivan</name> and
    <name type="person" ref="7" placement="note">Petr</name>.
  </p></body></text>
</TEI>
"""
    f = tmp_path / "tiny.xml"
    f.write_text(xml, encoding="utf-8")
    mentions = find_person_mentions(f)
    refs = sorted(m.ref for m in mentions)
    assert refs == ["42", "7"]
