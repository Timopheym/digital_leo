"""Round-trip a real TEI file through io_tei.write_tree and confirm structural
equality (we tolerate minor whitespace/serialization differences but require
the same set of elements, attributes, and visible text)."""
from __future__ import annotations

import pytest
from lxml import etree

from digital_leo.config import VENDOR_TEI
from digital_leo.io_tei import round_trip

KNOWN_LETTER = VENDOR_TEI / "texts" / "letters" / "v59_063_N_A_Nekrasovu.xml"

needs_corpus = pytest.mark.skipif(
    not KNOWN_LETTER.exists(),
    reason="vendor/TEI not cloned; run scripts/bootstrap.sh",
)


def _signature(tree: etree._ElementTree) -> tuple[int, int, str]:
    root = tree.getroot()
    n_elements = sum(1 for _ in root.iter())
    n_attrs = sum(len(el.attrib) for el in root.iter())
    text = " ".join(root.itertext()).split()
    return (n_elements, n_attrs, " ".join(text))


@needs_corpus
def test_round_trip_preserves_structure(tmp_path):
    out = round_trip(KNOWN_LETTER, tmp_path)
    assert out.exists()
    src_tree = etree.parse(str(KNOWN_LETTER))
    dst_tree = etree.parse(str(out))
    assert _signature(src_tree) == _signature(dst_tree)


def test_eval_score():
    from digital_leo.eval import score_mentions

    gold = [("Nekrasov", "9649"), ("Tolstoy", "13883")]
    pred = [("Nekrasov", "9649"), ("Wrong", "1")]
    s = score_mentions(gold, pred)
    assert s.tp == 1 and s.fp == 1 and s.fn == 1
    assert 0 < s.f1 < 1
