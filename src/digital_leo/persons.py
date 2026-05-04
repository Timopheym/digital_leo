"""Load and index the Tolstoy Digital personList.xml."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .config import NS, PERSON_LIST, TEI_NS, XML_NS


@dataclass
class Person:
    id: str
    main_name: str
    surname: str | None = None
    forenames: list[str] = field(default_factory=list)
    patronym: str | None = None
    variants: list[str] = field(default_factory=list)
    born: str | None = None
    died: str | None = None
    wikidata: str | None = None

    def all_names(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for n in [self.main_name, *self.variants]:
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out


def _text(el: etree._Element | None) -> str:
    if el is None:
        return ""
    return " ".join((el.text or "").split()).strip()


def _person_id(person_el: etree._Element) -> str | None:
    # Spec showed `id="15"`, but standard TEI uses xml:id. Handle both.
    val = person_el.get(f"{{{XML_NS}}}id") or person_el.get("id")
    return val


def _parse_person(p: etree._Element) -> Person | None:
    pid = _person_id(p)
    if not pid:
        return None

    main_el = p.find(f"t:persName[@type='main']", NS)
    if main_el is None:
        main_el = p.find("t:persName", NS)
    main_name = _text(main_el) if main_el is not None else ""

    surname = None
    forenames: list[str] = []
    patronym = None
    if main_el is not None:
        # In the sample, the lead text of <persName> is the full "Surname Forename Patronym"
        # then nested <forename> children carry parts (sort attr indicates order).
        for f in main_el.findall("t:forename", NS):
            t = _text(f)
            if not t:
                continue
            if f.get("type") == "patronym":
                patronym = t
            else:
                forenames.append(t)
        sn = main_el.find("t:surname", NS)
        if sn is not None:
            surname = _text(sn)

    # Variants: every other <persName> not type='main'
    variants: list[str] = []
    for pn in p.findall("t:persName", NS):
        if pn is main_el:
            continue
        t = _text(pn)
        if t:
            variants.append(t)
    # alternate name elements TEI also allows <name>
    for nm in p.findall("t:name", NS):
        t = _text(nm)
        if t:
            variants.append(t)

    born = died = None
    for ev in p.findall("t:event", NS):
        when = ev.get("when")
        if not when:
            continue
        if ev.get("type") == "born":
            born = when
        elif ev.get("type") == "died":
            died = when

    wikidata = main_el.get("ref") if main_el is not None else None
    if wikidata and not wikidata.startswith("Q"):
        wikidata = None

    return Person(
        id=pid,
        main_name=main_name,
        surname=surname,
        forenames=forenames,
        patronym=patronym,
        variants=variants,
        born=born,
        died=died,
        wikidata=wikidata,
    )


class PersonIndex:
    """In-memory index over personList.xml."""

    def __init__(self, persons: list[Person]):
        self._by_id: dict[str, Person] = {p.id: p for p in persons}
        self._by_name: dict[str, list[Person]] = defaultdict(list)
        self._by_surname: dict[str, list[Person]] = defaultdict(list)
        for p in persons:
            for name in p.all_names():
                self._by_name[name.lower()].append(p)
            if p.surname:
                self._by_surname[p.surname.lower()].append(p)

    def __len__(self) -> int:
        return len(self._by_id)

    def __iter__(self):
        return iter(self._by_id.values())

    def by_id(self, pid: str | int) -> Person | None:
        return self._by_id.get(str(pid))

    def by_exact_name(self, name: str) -> list[Person]:
        return list(self._by_name.get(name.lower(), []))

    def by_surname(self, surname: str) -> list[Person]:
        return list(self._by_surname.get(surname.lower(), []))

    @classmethod
    def load(cls, path: Path | None = None) -> "PersonIndex":
        path = path or PERSON_LIST
        if not path.exists():
            raise FileNotFoundError(
                f"personList.xml not found at {path}. "
                f"Run scripts/bootstrap.sh to clone the TEI corpus."
            )
        tree = etree.parse(str(path))
        root = tree.getroot()
        people: list[Person] = []
        for p in root.iter(f"{{{TEI_NS}}}person"):
            parsed = _parse_person(p)
            if parsed is not None:
                people.append(parsed)
        return cls(people)


def main() -> None:
    idx = PersonIndex.load()
    print(f"Loaded {len(idx)} persons from {PERSON_LIST}")
    for sample_id in ("9649", "13883", "13893"):
        p = idx.by_id(sample_id)
        if p:
            print(f"  {sample_id}: {p.main_name}  (variants: {len(p.variants)})")
        else:
            print(f"  {sample_id}: not found")


if __name__ == "__main__":
    main()
