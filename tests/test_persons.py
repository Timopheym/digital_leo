"""Tests for the personList loader.

Skips automatically if the corpus hasn't been cloned yet.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from digital_leo.config import PERSON_LIST, TEI_NS, XML_NS
from digital_leo.persons import PersonIndex


def _has_corpus() -> bool:
    return PERSON_LIST.exists()


needs_corpus = pytest.mark.skipif(
    not _has_corpus(), reason="vendor/TEI not cloned; run scripts/bootstrap.sh"
)


@needs_corpus
def test_loads_real_personlist():
    idx = PersonIndex.load()
    assert len(idx) > 100, f"expected >100 persons, got {len(idx)}"


@needs_corpus
def test_known_id_for_nekrasov():
    idx = PersonIndex.load()
    p = idx.by_id("9649")
    # Nekrasov is the recipient of v59_063_N_A_Nekrasovu.xml — must exist.
    assert p is not None, "person id=9649 (Nekrasov) missing from personList.xml"


@needs_corpus
def test_ids_reports_duplicates(tmp_path):
    """Surface duplicate IDs in personList — real corpus has some.

    We don't fail; we write the duplicates to output/reports/personlist_duplicates.txt
    so spec §7.3 (data validation) has a starting artifact.
    """
    from collections import Counter

    from digital_leo.config import OUTPUT_REPORTS

    tree = etree.parse(str(PERSON_LIST))
    ids: list[str] = []
    for p in tree.getroot().iter(f"{{{TEI_NS}}}person"):
        v = p.get(f"{{{XML_NS}}}id") or p.get("id")
        if v:
            ids.append(v)
    dups = [k for k, v in Counter(ids).items() if v > 1]
    OUTPUT_REPORTS.mkdir(parents=True, exist_ok=True)
    (OUTPUT_REPORTS / "personlist_duplicates.txt").write_text(
        f"total_ids={len(ids)} unique={len(set(ids))} duplicates={dups}\n"
    )
    # we still want a smoke check that we're parsing real data
    assert len(ids) > 1000


def test_synthetic_personlist(tmp_path: Path):
    """Schema-shape unit test: parser handles minimal fixture."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <standOff><listPerson>
    <person id="42">
      <persName type="main">Иванов Иван Иванович<forename sort="2">Иван</forename><forename sort="3" type="patronym">Иванович</forename><surname>Иванов</surname></persName>
      <persName>Иванов И. И.</persName>
      <event type="born" when="1900-01-01"/>
      <event type="died" when="1980-12-31"/>
    </person>
  </listPerson></standOff>
</TEI>
"""
    f = tmp_path / "tiny.xml"
    f.write_text(xml, encoding="utf-8")
    idx = PersonIndex.load(f)
    assert len(idx) == 1
    p = idx.by_id("42")
    assert p is not None
    assert "Иванов" in p.main_name
    assert p.surname == "Иванов"
    assert p.patronym == "Иванович"
    assert any("И. И." in v for v in p.variants)
    assert p.born == "1900-01-01"
    assert idx.by_surname("Иванов")[0].id == "42"
