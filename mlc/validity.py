from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .config import LABEL_NAMES, PRESENT
from .corpus import figure_type_classify, microscopy_score
from .rules import apply_rules


def _mask_spans(text: str, spans: Sequence[tuple]) -> str:
    chars = list(text)
    for s, e in spans:
        for i in range(max(0, int(s)), min(len(chars), int(e))):
            chars[i] = " "
    return "".join(chars)


def _failed_gate(caption: str, min_strong: int, keep_mixed: bool,
                 keep_structure: bool) -> str:
    if microscopy_score(caption)["n_strong"] < min_strong:
        return "lexical"
    _ftype, decision, _reason, _ev = figure_type_classify(
        caption, keep_mixed=keep_mixed, keep_structure=keep_structure)
    return "" if decision.startswith("keep") else "figure_type"


def verdict(dependence: float) -> str:
    if dependence >= 0.25:
        return "not estimable"
    if dependence >= 0.05:
        return "descriptive only"
    return "reportable finding"


def selection_dependence(rows: Sequence[Dict[str, Any]], min_strong: int = 1,
                         keep_mixed: bool = True, keep_structure: bool = False
                         ) -> List[Dict[str, Any]]:
    n = max(1, len(rows))
    cache = [(" ".join(str(r.get("caption", "")).split()),
              apply_rules(r.get("caption", "")))
             for r in rows]
    out: List[Dict[str, Any]] = []
    for lb in LABEL_NAMES:
        present = lost = lost_given_present = 0
        by_gate = {"lexical": 0, "figure_type": 0}
        for cap, res in cache:
            is_present = res.labels.get(lb) == PRESENT
            present += int(is_present)
            spans = [(e.start, e.end) for e in res.evidence.get(lb, [])]
            if not spans:
                continue
            gate = _failed_gate(_mask_spans(cap, spans), min_strong,
                                keep_mixed, keep_structure)
            if gate:
                lost += 1
                lost_given_present += int(is_present)
                by_gate[gate] += 1
        dependence = round(lost / n, 4)
        out.append({
            "label": lb,
            "prevalence": round(present / n, 4),
            "n_would_be_excluded": lost,
            "selection_dependence": dependence,
            "share_of_positives_that_drove_selection": (
                round(lost_given_present / present, 4) if present else None),
            "rejected_lexical": by_gate["lexical"],
            "rejected_figure_type": by_gate["figure_type"],
            "verdict": verdict(dependence),
        })
    return out
