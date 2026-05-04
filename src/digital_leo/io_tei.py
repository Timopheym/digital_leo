"""Safe write of annotated TEI to the parallel output tree."""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from .config import OUTPUT_TEI, VENDOR_TEI


def output_path_for(source: Path, output_root: Path | None = None) -> Path:
    """Map vendor/TEI/<rel> → output/tei/<rel> (preserves subtree)."""
    output_root = output_root or OUTPUT_TEI
    rel = source.resolve().relative_to(VENDOR_TEI.resolve())
    return output_root / rel


def write_tree(tree: etree._ElementTree, source: Path, output_root: Path | None = None) -> Path:
    out = output_path_for(source, output_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    tree.write(
        str(out),
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=False,
    )
    return out


def round_trip(source: Path, output_root: Path | None = None) -> Path:
    """Parse and re-serialize a TEI file unchanged. Used by the round-trip test."""
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    tree = etree.parse(str(source), parser)
    return write_tree(tree, source, output_root)
