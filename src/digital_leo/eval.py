"""Evaluation: precision / recall / F1 on (span_text, ref_id) pairs."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass
class Score:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


def score_mentions(gold: list[tuple[str, str]], pred: list[tuple[str, str]]) -> Score:
    """Compare bag-of-(text, ref) pairs. Multi-set semantics."""
    gold_c = Counter(gold)
    pred_c = Counter(pred)
    tp = sum((gold_c & pred_c).values())
    fp = sum((pred_c - gold_c).values())
    fn = sum((gold_c - pred_c).values())
    return Score(tp=tp, fp=fp, fn=fn)


def score_ids_only(gold_refs: list[str], pred_refs: list[str]) -> Score:
    return score_mentions(
        [(r, r) for r in gold_refs],
        [(r, r) for r in pred_refs],
    )
