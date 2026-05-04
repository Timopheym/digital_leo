"""Run a Langfuse experiment against the uploaded gold dataset.

Usage:
    uv run python -m digital_leo.scripts.run_experiment --approach rules --dataset tolstoy-ner-texts
    uv run python -m digital_leo.scripts.run_experiment --approach llm   --dataset tolstoy-ner-bio

For each dataset item the runner:
  1. Calls the chosen approach (rules or llm) on the item's text.
  2. Returns the prediction in the same shape as the item's expected_output.
  3. Computes precision / recall / F1 against expected_output.
  4. Logs traces, generations, and per-item scores to Langfuse, plus a
     run-level mean F1.
"""
from __future__ import annotations

from typing import Any

import typer
from rich import print

from ..eval import score_mentions
from ..persons import PersonIndex
from ..tracing import init_langfuse_env

app = typer.Typer(add_completion=False)

init_langfuse_env()
from langfuse import Evaluation, get_client, observe, propagate_attributes  # noqa: E402


# ---- Approach implementations ----------------------------------------------


_matcher_cache: dict[int, "object"] = {}


def _get_matcher(idx: PersonIndex):
    """Build StubMatcher once per index — pattern compilation is expensive."""
    from ..approach_rules.matcher import StubMatcher

    key = id(idx)
    if key not in _matcher_cache:
        _matcher_cache[key] = StubMatcher(idx)
    return _matcher_cache[key]


@observe(name="rules.predict", as_type="span")
def _predict_rules(text: str, kind: str, idx: PersonIndex) -> dict:
    """Run the rule-based matcher and shape the output by `kind`."""
    matcher = _get_matcher(idx)
    mentions = matcher.find_mentions(text)
    if kind == "texts":
        out = {"mentions": [{"surface": m.text, "ref": m.ref_id} for m in mentions]}
    else:  # bio
        out = {"person_refs": sorted({m.ref_id for m in mentions})}
    get_client().update_current_span(
        input={"chars": len(text), "kind": kind},
        output=out,
        metadata={"approach": "rules", "mention_count": len(mentions)},
    )
    return out


def _surname_token(p) -> str | None:
    """Best-effort surname for shortlisting.

    `PersonIndex.surname` is None for the bulk of personList.xml records (the
    XML stores `<persName>Тургенев Иван Сергеевич</persName>` with no nested
    `<surname>` child). Fall back to the leading whitespace-separated token of
    `main_name`, which is conventionally the surname in this corpus.
    """
    if p.surname:
        return p.surname
    if p.main_name:
        first = p.main_name.split()[0]
        return first if len(first) >= 4 else None
    return None


def _surname_in_text(surname: str, lc_text: str) -> bool:
    """Word-boundary substring check (start of word only, allows inflection)."""
    sn = surname.lower()
    pos = 0
    n = len(lc_text)
    while pos < n:
        i = lc_text.find(sn, pos)
        if i < 0:
            return False
        if i == 0 or not lc_text[i - 1].isalpha():
            return True
        pos = i + 1
    return False


@observe(name="llm.predict", as_type="span")
def _predict_llm(text: str, kind: str, idx: PersonIndex) -> dict:
    """Run the OpenAI-backed approach and shape the output by `kind`."""
    from ..approach_llm.client import OpenAiClient
    from ..approach_llm.prompts import SYSTEM_RU, user_prompt

    text = text[:12000]
    lc = text.lower()

    # Scan ALL persons whose surname appears (word-boundary prefix match), then
    # keep up to 60 candidates ranked by surname length descending. The earlier
    # "iterate-and-break-at-30" approach was alphabetically biased and missed
    # most target persons (e.g. Толстой/Тургенев/Руссо never reached).
    matches: list = []
    for p in idx:
        sn = _surname_token(p)
        if not sn or len(sn) < 4:
            continue
        if _surname_in_text(sn, lc):
            matches.append(p)
    # Sort by surname (clusters homonyms so the LLM can compare them) then by id.
    # Cap at 60 by *surname* — pick the 60 most distinctive (longest) surname
    # groups, then include all persons sharing those surnames.
    matches.sort(key=lambda p: ((_surname_token(p) or "").lower(), p.id))
    if len(matches) > 60:
        # group by surname, keep first 60 unique surnames ranked by length desc
        from collections import OrderedDict

        by_sn: "OrderedDict[str, list]" = OrderedDict()
        for p in sorted(matches, key=lambda p: (-len(_surname_token(p) or ""), p.id)):
            by_sn.setdefault((_surname_token(p) or "").lower(), []).append(p)
        kept: list = []
        for sn, group in by_sn.items():
            if len(kept) >= 60:
                break
            kept.extend(group)
        matches = sorted(kept, key=lambda p: ((_surname_token(p) or "").lower(), p.id))
    candidates = [
        {
            "id": p.id,
            "main_name": p.main_name,
            "born": p.born,
            "died": p.died,
        }
        for p in matches
    ]

    mentions: list[dict] = []
    if candidates:
        client = OpenAiClient()
        parsed, _ = client.chat_json(SYSTEM_RU, user_prompt(text, candidates))
        if isinstance(parsed, list):
            mentions = parsed
        elif isinstance(parsed, dict):
            if isinstance(parsed.get("mentions"), list):
                mentions = parsed["mentions"]
            elif any(k in parsed for k in ("ref_id", "text")):
                # Single-mention dict — wrap.
                mentions = [parsed]
            else:
                # Find first list-valued key.
                for v in parsed.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        mentions = v
                        break

    if kind == "texts":
        out = {
            "mentions": [
                {"surface": m.get("text", ""), "ref": str(m.get("ref_id", ""))}
                for m in mentions
                if m.get("ref_id")
            ]
        }
    else:
        out = {"person_refs": sorted({str(m["ref_id"]) for m in mentions if m.get("ref_id")})}
    get_client().update_current_span(
        input={"chars": len(text), "kind": kind, "candidate_count": len(candidates)},
        output=out,
        metadata={"approach": "llm"},
    )
    return out


# ---- Evaluators -------------------------------------------------------------


_SURFACE_PUNCT_RE = __import__("re").compile(r"[^\w\s-]", __import__("re").UNICODE)
_SURFACE_WS_RE = __import__("re").compile(r"\s+")


def _normalize_surface(s: str) -> str:
    """Case-/punctuation-/whitespace-/ё-insensitive surface normalization.

    Why: gold preserves the original capitalized inflected form
    ("Тургенева", "Л. Н. Толстой"), while predictions vary by case, dot
    spacing, and ё/е. Strict (surface, ref) F1 was penalising these as
    mismatches even when the ref was right. Normalize both sides before
    bagging.
    """
    s = s.lower().replace("ё", "е")
    s = _SURFACE_PUNCT_RE.sub(" ", s)
    s = _SURFACE_WS_RE.sub(" ", s).strip()
    return s


def _pairs(d: dict) -> list[tuple[str, str]]:
    """Strict bag: (normalized surface, ref) for texts, (ref, ref) for bio docs."""
    if "mentions" in d:
        return [
            (_normalize_surface(m.get("surface", "")), str(m.get("ref", "")))
            for m in d["mentions"]
        ]
    if "person_refs" in d:
        return [(r, r) for r in d["person_refs"]]
    return []


def _refs(d: dict) -> list[str]:
    """Relaxed bag: refs only (ignores surface form)."""
    if "mentions" in d:
        return [str(m.get("ref", "")) for m in d["mentions"] if m.get("ref")]
    if "person_refs" in d:
        return list(d["person_refs"])
    return []


def _eval_precision(*, output: Any, expected_output: Any, **_: Any) -> Evaluation:
    s = score_mentions(_pairs(expected_output or {}), _pairs(output or {}))
    return Evaluation(name="precision", value=s.precision, comment=f"tp={s.tp} fp={s.fp}")


def _eval_recall(*, output: Any, expected_output: Any, **_: Any) -> Evaluation:
    s = score_mentions(_pairs(expected_output or {}), _pairs(output or {}))
    return Evaluation(name="recall", value=s.recall, comment=f"tp={s.tp} fn={s.fn}")


def _eval_f1(*, output: Any, expected_output: Any, **_: Any) -> Evaluation:
    s = score_mentions(_pairs(expected_output or {}), _pairs(output or {}))
    return Evaluation(name="f1", value=s.f1, comment=f"tp={s.tp} fp={s.fp} fn={s.fn}")


def _eval_f1_refs(*, output: Any, expected_output: Any, **_: Any) -> Evaluation:
    """Refs-only F1: forgives surface/lowercasing mismatches."""
    from collections import Counter

    g = Counter(_refs(expected_output or {}))
    p = Counter(_refs(output or {}))
    tp = sum((g & p).values())
    fp = sum((p - g).values())
    fn = sum((g - p).values())
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return Evaluation(name="f1_refs", value=f1, comment=f"tp={tp} fp={fp} fn={fn}")


def _mean_value(item_results: list, score_name: str) -> float | None:
    vals = [
        e.value
        for r in item_results
        for e in getattr(r, "evaluations", [])
        if e.name == score_name
    ]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _run_mean_f1(*, item_results: list, **_: Any) -> Evaluation:
    v = _mean_value(item_results, "f1")
    return Evaluation(name="mean_f1", value=v if v is not None else 0.0)


def _run_mean_f1_refs(*, item_results: list, **_: Any) -> Evaluation:
    v = _mean_value(item_results, "f1_refs")
    return Evaluation(name="mean_f1_refs", value=v if v is not None else 0.0)


# ---- Entrypoint -------------------------------------------------------------


def _build_task(approach: str):
    idx = PersonIndex.load()

    def task(*, item: Any, **_: Any) -> dict:
        # `item` is a langfuse DatasetItem when launched from `dataset.run_experiment`;
        # for ad-hoc local data it would be a dict, so support both.
        raw = item.input if hasattr(item, "input") else item["input"]
        text = raw["text"]
        kind = raw["kind"]
        section = raw.get("section", "")
        with propagate_attributes(
            tags=[f"approach:{approach}", f"kind:{kind}", f"section:{section}"],
            metadata={"approach": approach, "kind": kind, "section": section},
        ):
            if approach == "rules":
                return _predict_rules(text, kind, idx)
            return _predict_llm(text, kind, idx)

    return task


@app.command()
def main(
    approach: str = typer.Option(..., "--approach", help="rules | llm"),
    dataset: str = typer.Option(..., "--dataset", help="Langfuse dataset name"),
    run_name: str = typer.Option(None, "--run-name", help="defaults to <approach>-<dataset>-<timestamp>"),
    max_concurrency: int = typer.Option(4, "--max-concurrency"),
) -> None:
    if approach not in {"rules", "llm"}:
        raise typer.BadParameter("approach must be 'rules' or 'llm'")

    from datetime import datetime, timezone

    if not run_name:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_name = f"{approach}-{dataset}-{ts}"

    lf = get_client()
    ds = lf.get_dataset(dataset)
    print(f"loaded {len(ds.items)} items from dataset [bold]{dataset}[/bold]")

    # `dataset.run_experiment` auto-creates a Langfuse DatasetRun and links each
    # task trace to the corresponding DatasetItem so the run shows up under
    # Datasets → <name> → Runs in the UI.
    result = ds.run_experiment(
        name=run_name,
        description=f"approach={approach} dataset={dataset}",
        task=_build_task(approach),
        evaluators=[_eval_precision, _eval_recall, _eval_f1, _eval_f1_refs],
        run_evaluators=[_run_mean_f1, _run_mean_f1_refs],
        max_concurrency=max_concurrency,
    )
    lf.flush()
    print(result.format())


if __name__ == "__main__":
    app()
