from __future__ import annotations

import re
from functools import lru_cache
from statistics import median
from typing import Any, Dict, List, Sequence, Tuple

from .config import LABEL_NAMES, PRESENT
from .rules import apply_rules

Span = Tuple[int, int]

def locate_phrase(caption: str, phrase: str) -> List[Span]:
    phrase = " ".join(str(phrase or "").split())
    if not phrase:
        return []
    pattern = r"\s+".join(re.escape(tok) for tok in phrase.split())
    return [m.span() for m in re.finditer(pattern, caption, re.IGNORECASE)]

def _merge(spans: Sequence[Span]) -> List[Span]:
    out: List[Span] = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out

def reference_spans_from_sheet(rows: Sequence[Dict[str, str]],
                               captions: Dict[str, str]
                               ) -> Dict[Tuple[str, str], List[Span]]:
    out: Dict[Tuple[str, str], List[Span]] = {}
    for r in rows:
        lid = str(r.get("legend_id", "")).strip()
        cap = captions.get(lid, "")
        if not lid or not cap:
            continue
        cap = " ".join(str(cap).split())
        for lb in LABEL_NAMES:
            cell = str(r.get(f"span_{lb}", "")).strip()
            if not cell:
                continue
            spans: List[Span] = []
            for phrase in cell.split("|"):
                spans.extend(locate_phrase(cap, phrase.strip()))
            if spans:
                out[(lid, lb)] = _merge(spans)
    return out

def span_sheet(rows: Sequence[Dict[str, Any]], max_chars: int = 0
               ) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        cap = str(r.get("caption", ""))
        rec: Dict[str, Any] = {"legend_id": r["legend_id"],
                               "caption": cap[:max_chars] if max_chars else cap}
        for lb in LABEL_NAMES:
            rec[f"span_{lb}"] = ""
        rec["annotator_note"] = ""
        out.append(rec)
    return out

def _iou(a: Span, b: Span) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union else 0.0

@lru_cache(maxsize=4096)
def _all_predicted_spans(caption: str) -> Dict[str, Tuple[Span, ...]]:
    res = apply_rules(caption, allow_unclear=False)
    return {lb: tuple(_merge([(int(e.start), int(e.end))
                              for e in res.evidence.get(lb, [])]))
            for lb in LABEL_NAMES}

def _predicted_spans(caption: str, label: str) -> List[Span]:
    return list(_all_predicted_spans(caption).get(label, ()))

def evaluate_spans(rows: Sequence[Dict[str, Any]],
                   references: Dict[Tuple[str, str], List[Span]],
                   label_prefix: str, iou_threshold: float = 0.5
                   ) -> Dict[str, Any]:
    per_label: Dict[str, Dict[str, Any]] = {}
    for lb in LABEL_NAMES:
        exact = partial = 0
        matched_ref = 0
        n_ref = n_pred = 0
        ious: List[float] = []
        pred_lens: List[int] = []
        ref_lens: List[int] = []
        tp_labels = tp_with_span = 0
        for r in rows:
            key = (r["legend_id"], lb)
            ref = references.get(key)
            if ref is None:
                continue
            cap = " ".join(str(r.get("caption", "")).split())
            pred = _predicted_spans(cap, lb)
            n_ref += len(ref)
            n_pred += len(pred)
            ref_lens.extend(g[1] - g[0] for g in ref)
            pred_lens.extend(p[1] - p[0] for p in pred)
            gold_present = str(r.get(f"{label_prefix}_{lb}", "")).upper() == PRESENT
            if gold_present and pred:
                tp_labels += 1
                if any(_iou(p, g) > 0 for p in pred for g in ref):
                    tp_with_span += 1
            for p in pred:
                best = max((_iou(p, g) for g in ref), default=0.0)
                if best > 0:
                    partial += 1
                    ious.append(best)
                if any(p == g for g in ref):
                    exact += 1
            matched_ref += sum(1 for g in ref if any(_iou(p, g) > 0 for p in pred))
        per_label[lb] = {
            "n_reference_spans": n_ref,
            "n_predicted_spans": n_pred,
            "exact_matches": exact,
            "partial_matches": partial,
            "matched_reference_spans": matched_ref,
            "span_precision_partial": round(partial / n_pred, 4) if n_pred else None,
            "span_recall_partial": (round(matched_ref / n_ref, 4)
                                    if n_ref else None),
            "span_precision_exact": round(exact / n_pred, 4) if n_pred else None,
            "mean_iou_of_matches": round(sum(ious) / len(ious), 4) if ious else None,
            "label_tp": tp_labels,
            "label_tp_with_correct_span": tp_with_span,
            "right_for_the_right_reason": (round(tp_with_span / tp_labels, 4)
                                           if tp_labels else None),
            "median_pred_span_chars": (round(median(pred_lens), 1)
                                       if pred_lens else None),
            "max_pred_span_chars": max(pred_lens) if pred_lens else None,
            "median_ref_span_chars": (round(median(ref_lens), 1)
                                      if ref_lens else None),
        }
    scored = [lb for lb in LABEL_NAMES if per_label[lb]["n_reference_spans"]]
    macro = {}
    for key in ("span_precision_partial", "span_recall_partial",
                "right_for_the_right_reason"):
        vals = [per_label[lb][key] for lb in scored if per_label[lb][key] is not None]
        macro[key] = round(sum(vals) / len(vals), 4) if vals else None
    return {"per_label": per_label, "macro": macro, "labels_scored": scored,
            "n_legends_with_spans": len({k[0] for k in references})}

def to_rows(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = [{"label": lb, **res["per_label"][lb]} for lb in LABEL_NAMES]
    out.append({"label": "MACRO", **res["macro"]})
    return out
