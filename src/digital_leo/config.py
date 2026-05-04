from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_TEI = REPO_ROOT / "vendor" / "TEI"
PERSON_LIST = VENDOR_TEI / "reference" / "personList.xml"
BIBLLIST_BIO = VENDOR_TEI / "reference" / "bibllist_bio.xml"
TEXTS_DIR = VENDOR_TEI / "texts"
# In the actual repo, author folders live under tolstoy-bio/tolstoy_bio/<author>/data/xml/
TOLSTOY_BIO_DIR = VENDOR_TEI / "tolstoy-bio" / "tolstoy_bio"

DATA_DIR = REPO_ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
SAMPLE_MANIFEST = SAMPLE_DIR / "manifest.json"
GOLD_DIR = DATA_DIR / "gold"

OUTPUT_DIR = REPO_ROOT / "output"
# Mirrors the full vendor/TEI tree (so output/tei/texts/... and output/tei/tolstoy-bio/...).
OUTPUT_TEI = OUTPUT_DIR / "tei"
# Kept for back-compat with existing imports.
OUTPUT_TEXTS = OUTPUT_TEI
OUTPUT_BIO_CSV = OUTPUT_DIR / "bio_csv"
OUTPUT_REPORTS = OUTPUT_DIR / "reports"

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"t": TEI_NS, "xml": XML_NS}


def load_env() -> None:
    load_dotenv(REPO_ROOT / ".env")


def openai_api_key() -> str | None:
    load_env()
    return os.environ.get("OPENAI_API_KEY")


def openai_model() -> str:
    load_env()
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
