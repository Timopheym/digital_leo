"""Gold dataset extraction tests.

Synthetic-fixture tests run anywhere. Real-corpus tests skip without
vendor/TEI cloned and without a built sample manifest.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_leo.config import (
    BIBLLIST_BIO,
    PERSON_LIST,
    SAMPLE_MANIFEST,
    VENDOR_TEI,
)
from digital_leo.corpus import CorpusFile
from digital_leo.gold import (
    BibllistBioIndex,
    collect_orphans,
    extract_bio_gold,
    extract_text_gold,
    split_for,
)
from digital_leo.persons import PersonIndex


# ---- Synthetic fixtures (always run) ---------------------------------------


def test_split_for_is_deterministic():
    a = split_for("texts/letters/foo.xml")
    b = split_for("texts/letters/foo.xml")
    assert a == b
    assert a in {"dev", "test"}


def test_split_for_distributes_roughly():
    """SHA-256 hash should give ~20% test on a moderate sample of paths."""
    paths = [f"texts/letters/v{i:03d}.xml" for i in range(500)]
    test = sum(1 for p in paths if split_for(p) == "test")
    # Loose bounds — we only care that it's not absurdly skewed.
    assert 60 <= test <= 160, f"test ratio off: {test}/500"


def test_extract_text_gold_synthetic(tmp_path: Path):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <text><body><p>
    Hello, <name placement="text" ref="42" type="person">Иван</name> and
    <name placement="comments" ref="7" type="person">Петр</name>.
  </p></body></text>
</TEI>
"""
    f = tmp_path / "tiny.xml"
    f.write_text(xml, encoding="utf-8")
    cf = CorpusFile(
        path=f,
        kind="texts",
        section="letters",
        rel_to_vendor=Path("texts/letters/tiny.xml"),
    )
    # Patch VENDOR_TEI lookup by passing a CorpusFile whose path may not be under
    # vendor — extract_text_gold uses file.path directly, not relative_to().
    mentions = extract_text_gold(cf)
    refs = sorted(m.ref for m in mentions)
    assert refs == ["42", "7"]
    surfaces = {m.surface for m in mentions}
    assert "Иван" in surfaces and "Петр" in surfaces
    placements = {m.placement for m in mentions}
    assert placements == {"text", "comments"}
    assert all(m.split in {"dev", "test"} for m in mentions)


def test_bibllist_bio_index_synthetic(tmp_path: Path):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <text><body><list>
    <item>
      <relatedItem>
        <ref xml:id="goldenweiser-diaries_1906-01-30_1906-01-30"/>
        <relation ref="9649" type="person"/>
        <relation ref="13883" type="person"/>
        <relation ref="EMPTY" type="person"/>
        <relation ref="EMPTY" type="works"/>
      </relatedItem>
      <relatedItem>
        <ref xml:id="other_doc"/>
        <relation ref="9649" type="person"/>
        <relation ref="9649" type="person"/>
      </relatedItem>
    </item>
  </list></body></text>
</TEI>
"""
    f = tmp_path / "bib.xml"
    f.write_text(xml, encoding="utf-8")
    idx = BibllistBioIndex.load(f)
    assert len(idx) == 2
    refs = idx.lookup("goldenweiser-diaries_1906-01-30_1906-01-30")
    assert refs == ["9649", "13883"]  # EMPTY filtered, sorted by length then string
    # Dedup
    assert idx.lookup("other_doc") == ["9649"]
    # Missing
    assert idx.lookup("nope") is None


def test_extract_bio_gold_uses_stem(tmp_path: Path):
    bib = tmp_path / "bib.xml"
    bib.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <text><body><list><item>
    <relatedItem>
      <ref xml:id="my-doc"/>
      <relation ref="42" type="person"/>
    </relatedItem>
  </item></list></body></text>
</TEI>
""",
        encoding="utf-8",
    )
    idx = BibllistBioIndex.load(bib)
    bio_file = tmp_path / "my-doc.xml"
    bio_file.write_text("<x/>", encoding="utf-8")
    cf = CorpusFile(
        path=bio_file,
        kind="bio",
        section="goldenweiser",
        rel_to_vendor=Path("tolstoy-bio/tolstoy_bio/goldenweiser/data/xml/my-doc.xml"),
    )
    doc = extract_bio_gold(cf, idx)
    assert doc.found_in_bibllist is True
    assert doc.person_refs == ["42"]
    assert doc.xml_id == "my-doc"


def test_collect_orphans_with_synthetic_index(tmp_path: Path):
    plist = tmp_path / "p.xml"
    plist.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <standOff><listPerson>
    <person id="42"><persName type="main">Foo</persName></person>
  </listPerson></standOff>
</TEI>
""",
        encoding="utf-8",
    )
    idx = PersonIndex.load(plist)
    orphans = collect_orphans(["42", "7", "999", "42"], idx)
    assert orphans == ["7", "999"]


# ---- Real corpus tests -----------------------------------------------------


needs_corpus = pytest.mark.skipif(
    not (PERSON_LIST.exists() and BIBLLIST_BIO.exists()),
    reason="vendor/TEI not cloned; run scripts/bootstrap.sh",
)

needs_sample = pytest.mark.skipif(
    not SAMPLE_MANIFEST.exists(),
    reason="sample manifest missing; run python -m digital_leo.scripts.build_sample",
)


@needs_corpus
def test_real_bibllist_bio_loads():
    idx = BibllistBioIndex.load()
    # Corpus has ~32k <relatedItem> entries.
    assert len(idx) > 1000


@needs_corpus
def test_real_known_letter_extracts_three_refs():
    f = VENDOR_TEI / "texts" / "letters" / "v59_063_N_A_Nekrasovu.xml"
    cf = CorpusFile(
        path=f,
        kind="texts",
        section="letters",
        rel_to_vendor=f.relative_to(VENDOR_TEI),
    )
    mentions = extract_text_gold(cf)
    refs = {m.ref for m in mentions}
    assert {"9649", "13883", "13893"} <= refs


@needs_corpus
@needs_sample
def test_built_gold_artifacts_are_valid_jsonl():
    """If build_gold.py has been run, validate the JSONL it wrote."""
    from digital_leo.gold import GOLD_BIO_JSONL, GOLD_TEXTS_JSONL, load_text_gold

    if not GOLD_TEXTS_JSONL.exists():
        pytest.skip("gold not built yet; run python -m digital_leo.scripts.build_gold")
    rows = load_text_gold(GOLD_TEXTS_JSONL)
    assert rows, "texts gold is empty"
    # Every row should have a non-empty surface and ref, and a valid split.
    for r in rows[:50]:
        assert r.surface and r.ref
        assert r.split in {"dev", "test"}
    # bio.jsonl is line-per-doc; basic shape check.
    if GOLD_BIO_JSONL.exists():
        for line in GOLD_BIO_JSONL.read_text(encoding="utf-8").splitlines()[:20]:
            d = json.loads(line)
            assert "person_refs" in d and "split" in d
