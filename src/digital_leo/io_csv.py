"""Emit bio CSVs in the format expected by
vendor/TEI/utils/import_csv_database_dump_to_bibllist_bio.py.

Columns observed in that script (semicolon-delimited):
  dates;hrdate;opener;uid;bibid;bibtext;persons;works;texts;places;incal;timespan

`persons` (and works/texts/places) are Python literal lists of IDs:
    "[123, 456]"  or  "[]"
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

CSV_COLUMNS = [
    "dates",
    "hrdate",
    "opener",
    "uid",
    "bibid",
    "bibtext",
    "persons",
    "works",
    "texts",
    "places",
    "incal",
    "timespan",
]


@dataclass
class BioCsvRow:
    uid: str
    bibid: str
    persons: list[str] = field(default_factory=list)
    works: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    hrdate: str = ""
    opener: str = ""
    bibtext: str = ""
    incal: bool = False
    timespan: str = ""

    def as_csv(self) -> dict[str, str]:
        def _list(xs: list) -> str:
            return "[" + ", ".join(repr(x) for x in xs) + "]"

        return {
            "dates": _list(self.dates),
            "hrdate": self.hrdate,
            "opener": self.opener,
            "uid": self.uid,
            "bibid": self.bibid,
            "bibtext": self.bibtext,
            "persons": _list(self.persons),
            "works": _list(self.works),
            "texts": _list(self.texts),
            "places": _list(self.places),
            "incal": str(self.incal),
            "timespan": self.timespan,
        }


def write_bio_csv(rows: list[BioCsvRow], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, delimiter=";")
        writer.writeheader()
        for r in rows:
            writer.writerow(r.as_csv())
    return path
