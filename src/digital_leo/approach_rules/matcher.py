"""Rule-based person matcher.

Generates name variants per person (canonical, surname-only, "F. Surname",
"Forename Surname", "Surname F. P.", plus XML-declared variants) and matches
them against the input text with word boundaries. Russian inflectional
endings on the surname-only variant are tolerated via a `[а-яё]{0,4}` tail.

The matcher returns the original surface from the text (case-preserved), not
the lowercased dictionary form, so the strict `(surface, ref)` evaluator can
reward exact gold-set matches.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..persons import Person, PersonIndex


@dataclass
class Mention:
    text: str  # original surface from input text
    ref_id: str
    confidence: float
    rationale: str = ""


_CYRILLIC_TAIL = r"[а-яё]{0,4}"

# Adjectival-surname suffixes whose base form differs from inflected forms.
# Stripping yields a stem like "Лобачевск" which then matches "Лобачевск[ого|ому|им|ая|ой|ое]"
# via the inflectional tail. Restricted to highly distinctive consonant-cluster
# endings to avoid false positives on common adjectives (e.g. "толст" + ой/ый).
_ADJ_SURNAME_SUFFIXES = ("ский", "ской", "цкий", "цкой", "ская", "цкая")


def _surname_stem(s: str) -> str:
    low = s.lower()
    for suf in _ADJ_SURNAME_SUFFIXES:
        if low.endswith(suf) and len(s) > len(suf) + 2:
            return s[: -len(suf) + 2]  # keep "ск" / "цк" stem
    return s


_PATRONYM_SUFFIXES = (
    "ович", "евич", "ёвич",
    "овна", "евна", "ёвна",
    "ична", "инична",
)


def _has_patronym_suffix(s: str) -> bool:
    sl = s.lower()
    return any(sl.endswith(suf) for suf in _PATRONYM_SUFFIXES)


def _name_components(p: Person) -> tuple[str | None, list[str]]:
    """Extract (surname, forenames) from `main_name` with patronym-aware reordering.

    Two common orders in this corpus:
    - "Surname Forename Patronym" — the dominant format
      (e.g. "Толстой Лев Николаевич")
    - "Forename Patronym Surname" — used for some entries where parts[1] is
      a recognisable patronym (e.g. "Надежда Дмитриевна Покровская").
      Without reordering, parts[0]="Надежда" gets treated as a surname and
      every occurrence of the common noun "надежда" matches as a person.
    """
    parts = p.main_name.split() if p.main_name else []
    if not parts:
        return None, []
    if len(parts) >= 3 and _has_patronym_suffix(parts[1]):
        return parts[2], [parts[0]]
    return parts[0], parts[1:]


def _surname_token(p: Person) -> str | None:
    """Best-effort surname token.

    Prefers the XML-declared `<surname>` (rare in this corpus), then falls
    back to a patronym-aware split of `main_name`.
    """
    if p.surname:
        return p.surname
    surname, _ = _name_components(p)
    if surname and len(surname) >= 4:
        return surname
    return None


def _initial(s: str) -> str:
    return f"{s[:1]}." if s else ""


def _name_variants(p: Person) -> list[str]:
    """Generate plausible surface variants for one person.

    Why: `personList.xml` typically records only the canonical
    "Surname Forename Patronym" form. Real text uses surname-alone, swapped
    "Forename Surname", and initial-prefixed variants. Without these, exact
    dictionary matching never fires on body text.
    """
    out: list[str] = []
    surname = _surname_token(p)
    if not surname:
        return out
    _, forenames = _name_components(p)

    out.append(p.main_name)
    out.append(surname)
    if forenames:
        out.append(f"{forenames[0]} {surname}")
        out.append(f"{surname} {forenames[0]}")
        out.append(f"{_initial(forenames[0])} {surname}")
        out.append(f"{surname} {_initial(forenames[0])}")
        if len(forenames) >= 2:
            out.append(f"{forenames[0]} {forenames[1]} {surname}")  # F P S
            out.append(f"{_initial(forenames[0])} {_initial(forenames[1])} {surname}")
            out.append(f"{surname} {_initial(forenames[0])} {_initial(forenames[1])}")
    for v in p.variants:
        if v:
            out.append(v)
    return out


_CONTEXT_WINDOW = 80  # chars on each side of a hit for forename context


def _candidate_tokens(p: Person) -> set[str]:
    """Lowercased forename + initial tokens used to disambiguate this person.

    Limits to first forename + patronym (parts[1:3]) and strips punctuation,
    because some `main_name` fields trail a parenthetical or repeated surname
    (e.g. "Толстой Илья Андреевич, брат А. А. Толстой") that would otherwise
    leak junk tokens.
    """
    surname, forenames = _name_components(p)
    if not surname:
        return set()
    surname_l = surname.lower()
    out: set[str] = set()
    for fn in forenames[:2]:
        cleaned = re.sub(r"[^\w]", "", fn, flags=re.UNICODE)
        if len(cleaned) < 2:
            continue
        fn_l = cleaned.lower()
        if fn_l == surname_l:
            continue
        out.add(fn_l)
        out.add(f"{fn_l[0]}.")
    return out


def _distinguishing_tokens(persons: list[Person]) -> list[set[str]]:
    """Per-person tokens that no other candidate in the group shares."""
    all_toks = [_candidate_tokens(p) for p in persons]
    out: list[set[str]] = []
    for i, toks in enumerate(all_toks):
        others: set[str] = set()
        for j, t in enumerate(all_toks):
            if j != i:
                others |= t
        out.append(toks - others)
    return out


def _token_in_window(tok: str, window_lc: str) -> bool:
    """Check token presence with morphology-aware boundary rules.

    - "л." / "н." → exact dotted form
    - longer tokens (≥4 chars, e.g. "николаевич") → word-prefix (matches
      "николаевича", "николаевичу")
    - short bare tokens (e.g. "лев") → exact word boundary on both sides
      (avoids "левый", "левее")
    """
    if tok.endswith("."):
        return re.search(rf"\b{re.escape(tok)}", window_lc) is not None
    if len(tok) >= 4:
        return re.search(rf"\b{re.escape(tok)}", window_lc) is not None
    return re.search(rf"\b{re.escape(tok)}\b", window_lc) is not None


class StubMatcher:
    """Variant-aware dictionary matcher with morphology tolerance and
    forename-context disambiguation for shared surnames.
    """

    def __init__(self, idx: PersonIndex):
        self.idx = idx
        variant_to_persons: dict[str, list[Person]] = {}
        for p in idx:
            for v in _name_variants(p):
                if len(v) < 4:
                    continue
                variant_to_persons.setdefault(v, []).append(p)

        # Each entry: (pattern, candidates, distinguishing-tokens-per-candidate).
        # When `candidates` has length 1 the disambiguator is a no-op fast path;
        # otherwise we use forename/patronym tokens in a ±80 char window to
        # pick which candidate to credit.
        self._patterns: list[
            tuple[re.Pattern[str], list[Person], list[set[str]]]
        ] = []
        for variant, persons in variant_to_persons.items():
            if " " not in variant and "." not in variant:
                # Surname alone — require ≥5 chars to avoid "Поль/Пост"-class
                # collisions, then strip adjectival ending and tolerate the
                # Russian inflectional tail.
                if len(variant) < 5:
                    continue
                stem = _surname_stem(variant)
                pat = re.compile(
                    rf"\b{re.escape(stem)}{_CYRILLIC_TAIL}\b",
                    re.IGNORECASE,
                )
            else:
                # Use lookbehind/lookahead instead of \b: \b doesn't fire at a
                # punctuation-to-space transition, so "Толстой Л. Н." would fail
                # to match in "Толстой Л. Н. Дневник".
                pat = re.compile(
                    rf"(?<!\w){re.escape(variant)}(?!\w)",
                    re.IGNORECASE,
                )
            distinguishing = (
                [set()] if len(persons) == 1 else _distinguishing_tokens(persons)
            )
            self._patterns.append((pat, persons, distinguishing))

    @staticmethod
    def _pick(
        window_lc: str, candidates: list[Person], distinguishing: list[set[str]]
    ) -> Person | None:
        scores: list[tuple[int, Person]] = []
        for cand, toks in zip(candidates, distinguishing):
            score = sum(1 for t in toks if _token_in_window(t, window_lc))
            scores.append((score, cand))
        scores.sort(key=lambda s: (-s[0], s[1].id))
        if not scores or scores[0][0] == 0:
            return None
        if len(scores) > 1 and scores[0][0] == scores[1][0]:
            return None  # tie — refuse to guess
        return scores[0][1]

    def find_mentions(self, text: str) -> list[Mention]:
        if not text:
            return []
        text_lc = text.lower()
        hits_by_person: dict[str, list[tuple[int, int, str]]] = {}
        for pat, persons, distinguishing in self._patterns:
            for m in pat.finditer(text):
                if len(persons) == 1:
                    chosen = persons[0]
                else:
                    lo = max(0, m.start() - _CONTEXT_WINDOW)
                    hi = min(len(text), m.end() + _CONTEXT_WINDOW)
                    chosen = self._pick(text_lc[lo:hi], persons, distinguishing)
                    if chosen is None:
                        continue
                hits_by_person.setdefault(chosen.id, []).append(
                    (m.start(), m.end(), m.group(0))
                )

        out: list[Mention] = []
        for pid, hits in hits_by_person.items():
            hits.sort(key=lambda t: -(t[1] - t[0]))  # longest first
            kept: list[tuple[int, int, str]] = []
            for start, end, surf in hits:
                if any(not (end <= ks or start >= ke) for ks, ke, _ in kept):
                    continue
                kept.append((start, end, surf))
            for start, end, surf in kept:
                out.append(
                    Mention(
                        text=surf,
                        ref_id=pid,
                        confidence=0.5,
                        rationale="variant dictionary match",
                    )
                )
        return out
