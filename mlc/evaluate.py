from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from fractions import Fraction
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .config import (LABEL_NAMES, NOT_DETECTED, PRESENT, RANDOM_SEED,
                     SILVER_SPLIT_FRACTIONS, UNCLEAR)

def prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f

def confusion(y_true: np.ndarray, y_pred: np.ndarray, mask: np.ndarray, j: int
              ) -> Tuple[int, int, int, int]:
    keep = mask[:, j]
    t, p = y_true[keep, j], y_pred[keep, j]
    tp = int(((t == 1) & (p == 1)).sum())
    fp = int(((t == 0) & (p == 1)).sum())
    fn = int(((t == 1) & (p == 0)).sum())
    tn = int(((t == 0) & (p == 0)).sum())
    return tp, fp, fn, tn

def _mcc(tp: int, fp: int, fn: int, tn: int):
    if tp + fp + fn + tn == 0:
        return None
    num = tp * tn - fp * fn
    den = float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if den <= 0:
        return 0.0
    return round(num / (den ** 0.5), 4)

def evaluate(y_true, y_pred, mask) -> Dict[str, Any]:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    mask = np.asarray(mask, dtype=bool)

    per_label: Dict[str, Dict[str, Any]] = {}
    TP = FP = FN = 0
    scored: List[float] = []
    undefined: List[str] = []
    for j, lb in enumerate(LABEL_NAMES):
        tp, fp, fn, tn = confusion(y_true, y_pred, mask, j)
        p, r, f = prf(tp, fp, fn)
        n = tp + fp + fn + tn
        defined = (tp + fp + fn) > 0
        per_label[lb] = {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": n,
            "support": tp + fn,
            "precision": round(p, 4) if defined else None,
            "recall": round(r, 4) if defined else None,
            "f1": round(f, 4) if defined else None,
            "accuracy": round((tp + tn) / n, 4) if n else None,
            "mcc": _mcc(tp, fp, fn, tn),
            "defined": defined,
        }
        if defined:
            scored.append(f)
        else:
            undefined.append(lb)
        TP += tp; FP += fp; FN += fn

    macro_f1 = float(np.mean(scored)) if scored else 0.0
    mccs = [per_label[lb]["mcc"] for lb in LABEL_NAMES
            if per_label[lb].get("mcc") is not None]
    macro_mcc = round(float(np.mean(mccs)), 4) if mccs else None
    mp, mr, mf = prf(TP, FP, FN)
    hamming = float((y_true[mask] != y_pred[mask]).mean()) if mask.any() else None
    full = mask.all(axis=1)
    subset_acc = (float((y_true[full] == y_pred[full]).all(axis=1).mean())
                  if full.any() else None)
    return {
        "per_label": per_label,
        "macro_f1": round(macro_f1, 4),
        "macro_mcc": macro_mcc,
        "macro_precision": round(float(np.mean(
            [per_label[lb]["precision"] for lb in LABEL_NAMES
             if per_label[lb]["defined"]] or [0.0])), 4),
        "macro_recall": round(float(np.mean(
            [per_label[lb]["recall"] for lb in LABEL_NAMES
             if per_label[lb]["defined"]] or [0.0])), 4),
        "micro_precision": round(mp, 4), "micro_recall": round(mr, 4),
        "micro_f1": round(mf, 4),
        "hamming_loss": None if hamming is None else round(hamming, 4),
        "subset_accuracy": None if subset_acc is None else round(subset_acc, 4),
        "labels_scored": len(scored),
        "labels_undefined": undefined,
    }

def bootstrap_macro_f1(y_true, y_pred, mask, n_boot: int = 2000,
                       seed: int = RANDOM_SEED) -> Dict[str, float]:
    y_true = np.asarray(y_true); y_pred = np.asarray(y_pred)
    mask = np.asarray(mask, dtype=bool)
    n, L = y_true.shape
    rng = np.random.default_rng(seed)

    tp_i = (mask & (y_true == 1) & (y_pred == 1)).astype(np.float64)
    fp_i = (mask & (y_true == 0) & (y_pred == 1)).astype(np.float64)
    fn_i = (mask & (y_true == 1) & (y_pred == 0)).astype(np.float64)

    idx = rng.integers(0, n, size=(n_boot, n))
    counts = np.zeros((n_boot, n), dtype=np.float64)
    rows = np.repeat(np.arange(n_boot), n)
    np.add.at(counts, (rows, idx.ravel()), 1.0)

    TP = counts @ tp_i
    FP = counts @ fp_i
    FN = counts @ fn_i
    with np.errstate(divide="ignore", invalid="ignore"):
        prec = np.where(TP + FP > 0, TP / (TP + FP), 0.0)
        rec = np.where(TP + FN > 0, TP / (TP + FN), 0.0)
        f1 = np.where(prec + rec > 0, 2 * prec * rec / (prec + rec), 0.0)
    defined = (TP + FP + FN) > 0
    with np.errstate(invalid="ignore"):
        macro = np.where(defined.any(axis=1),
                         (f1 * defined).sum(axis=1) / np.maximum(defined.sum(axis=1), 1),
                         0.0)
    lo, hi = np.percentile(macro, [2.5, 97.5])
    return {"macro_f1_mean": round(float(macro.mean()), 4),
            "ci95_low": round(float(lo), 4), "ci95_high": round(float(hi), 4)}

def mcnemar(y_true, pred_a, pred_b, mask, j: int) -> Dict[str, Any]:
    y_true = np.asarray(y_true); mask = np.asarray(mask, dtype=bool)
    pa = np.asarray(pred_a); pb = np.asarray(pred_b)
    keep = mask[:, j]
    t = y_true[keep, j]; a = pa[keep, j]; b = pb[keep, j]
    a_right = a == t
    b_right = b == t
    n01 = int((~a_right & b_right).sum())
    n10 = int((a_right & ~b_right).sum())
    n = n01 + n10
    if n == 0:
        return {"n01": 0, "n10": 0, "p_value": 1.0, "better": "tie"}
    k = min(n01, n10)
    numerator = sum(math.comb(n, i) for i in range(0, k + 1))
    p = min(1.0, float(Fraction(2 * numerator, 2 ** n)))
    better = "a" if n10 > n01 else ("b" if n01 > n10 else "tie")
    return {"n01": n01, "n10": n10, "p_value": round(p, 5), "better": better}

def holm_bonferroni(pvalues: Sequence[float]) -> List[float]:
    n = len(pvalues)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: pvalues[i])
    adjusted = [0.0] * n
    running = 0.0
    for rank, i in enumerate(order):
        val = min(1.0, (n - rank) * float(pvalues[i]))
        running = max(running, val)
        adjusted[i] = round(running, 5)
    return adjusted

def metrics_to_rows(model_name: str, split: str, res: Dict[str, Any]
                    ) -> List[Dict[str, Any]]:
    rows = []
    for lb in LABEL_NAMES:
        m = res["per_label"][lb]
        rows.append({"model": model_name, "split": split, "label": lb, **m})
    rows.append({"model": model_name, "split": split, "label": "MACRO",
                 "precision": res["macro_precision"], "recall": res["macro_recall"],
                 "f1": res["macro_f1"],
                 "mcc": res.get("macro_mcc")})
    rows.append({"model": model_name, "split": split, "label": "MICRO",
                 "precision": res["micro_precision"], "recall": res["micro_recall"],
                 "f1": res["micro_f1"],
                 "accuracy": res["subset_accuracy"]})
    return rows

def summary_table(all_results: Dict[str, Dict[str, Any]],
                  boots: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    out = []
    for name, res in all_results.items():
        b = boots.get(name, {})
        out.append({
            "model": name,
            "macro_f1": res["macro_f1"],
            "macro_f1_ci95": (f"[{b.get('ci95_low', '')}, {b.get('ci95_high', '')}]"
                              if b else ""),
            "macro_mcc": res.get("macro_mcc"),
            "micro_f1": res["micro_f1"],
            "macro_precision": res["macro_precision"],
            "macro_recall": res["macro_recall"],
            "subset_accuracy": res["subset_accuracy"],
            "hamming_loss": res["hamming_loss"],
        })
    return sorted(out, key=lambda r: -r["macro_f1"])

VALID = (PRESENT, NOT_DETECTED, UNCLEAR)

def _pairs(a: Sequence[str], b: Sequence[str]) -> List[Tuple[str, str]]:
    out = []
    for x, y in zip(a, b):
        xu, yu = str(x).upper(), str(y).upper()
        if xu in VALID and yu in VALID:
            out.append((xu, yu))
    return out

def raw_agreement(a: Sequence[str], b: Sequence[str]) -> Optional[float]:
    p = _pairs(a, b)
    return (sum(1 for x, y in p if x == y) / len(p)) if p else None

def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> Optional[float]:
    p = _pairs(a, b)
    if not p:
        return None
    n = len(p)
    cats = sorted({x for pair in p for x in pair})
    po = sum(1 for x, y in p if x == y) / n
    if len(cats) < 2:
        return None
    ca, cb = Counter(x for x, _ in p), Counter(y for _, y in p)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    if abs(1 - pe) < 1e-12:
        return None
    return (po - pe) / (1 - pe)

def pabak(a: Sequence[str], b: Sequence[str]) -> Optional[float]:
    po = raw_agreement(a, b)
    return None if po is None else 2 * po - 1

def krippendorff_alpha_nominal(matrix: Sequence[Sequence[Optional[str]]]
                               ) -> Optional[float]:
    if not matrix or not matrix[0]:
        return None
    n_items = len(matrix[0])
    units: List[List[str]] = []
    for j in range(n_items):
        vals = [str(row[j]).upper() for row in matrix
                if j < len(row) and row[j] is not None and str(row[j]).upper() in VALID]
        if len(vals) >= 2:
            units.append(vals)
    if not units:
        return None

    coincidence: Counter = Counter()
    n_total = 0.0
    for vals in units:
        m = len(vals)
        for i, x in enumerate(vals):
            for k, y in enumerate(vals):
                if i == k:
                    continue
                coincidence[(x, y)] += 1.0 / (m - 1)
        n_total += m

    cats = sorted({c for pair in coincidence for c in pair})
    if len(cats) < 2:
        return None
    observed = sum(coincidence[(c, c)] for c in cats)
    marginal = {c: sum(coincidence[(c, d)] for d in cats) for c in cats}
    if n_total <= 1:
        return None
    expected = sum(marginal[c] * (marginal[c] - 1) for c in cats) / (n_total - 1)
    do = 1 - observed / n_total
    de = 1 - expected / n_total
    if abs(de) < 1e-12:
        return None
    return 1 - do / de

def _r(x: Optional[float], nd: int = 4) -> Optional[float]:
    return None if x is None else round(float(x), nd)

def binary_targets(rows: Sequence[Dict[str, Any]], prefix: str
                   ) -> Tuple[List[List[int]], List[List[bool]]]:
    y, mask = [], []
    for r in rows:
        yi, mi = [], []
        for lb in LABEL_NAMES:
            v = str(r.get(f"{prefix}_{lb}", "")).upper()
            yi.append(1 if v == PRESENT else 0)
            mi.append(v in (PRESENT, NOT_DETECTED))
        y.append(yi)
        mask.append(mi)
    return y, mask

def group_split(rows: Sequence[Dict[str, Any]], fractions=None, seed: int = RANDOM_SEED
                ) -> Dict[str, List[Dict[str, Any]]]:
    fractions = fractions or SILVER_SPLIT_FRACTIONS
    by_article: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_article[str(r.get("source_id", r.get("legend_id")))].append(r)

    target_counts = {k: v * len(rows) for k, v in fractions.items()}
    corpus_rate = {}
    for j, lb in enumerate(LABEL_NAMES):
        pos = sum(1 for r in rows if str(r.get(f"silver_{lb}", "")).upper() == PRESENT)
        corpus_rate[lb] = pos / max(1, len(rows))

    aids = sorted(by_article)
    random.Random(seed).shuffle(aids)
    splits: Dict[str, List[Dict[str, Any]]] = {k: [] for k in fractions}
    pos_counts = {k: Counter() for k in fractions}

    for aid in aids:
        group = by_article[aid]
        best, best_cost = None, None
        for name in splits:
            n = len(splits[name])
            fill = n / max(1.0, target_counts[name])
            imbalance = 0.0
            for lb in LABEL_NAMES:
                have = pos_counts[name][lb] / max(1, n) if n else corpus_rate[lb]
                imbalance += abs(have - corpus_rate[lb])
            cost = fill * 3.0 + imbalance
            if best_cost is None or cost < best_cost:
                best, best_cost = name, cost
        splits[best].extend(group)
        for lb in LABEL_NAMES:
            pos_counts[best][lb] += sum(
                1 for r in group if str(r.get(f"silver_{lb}", "")).upper() == PRESENT)
    return splits

def build_splits(silver_rows: Sequence[Dict[str, Any]],
                 gold_rows: Sequence[Dict[str, Any]],
                 seed: int = RANDOM_SEED) -> Dict[str, Any]:
    gold_ids = {r["legend_id"] for r in gold_rows}
    gold_articles = {str(r.get("source_id", "")) for r in gold_rows}

    pool = [r for r in silver_rows
            if r["legend_id"] not in gold_ids
            and str(r.get("source_id", "")) not in gold_articles]

    split = group_split(pool, SILVER_SPLIT_FRACTIONS, seed=seed)
    return {
        "silver_train": split["train"],
        "silver_dev": split["dev"],
        "gold_test": list(gold_rows),
        "n_excluded_for_gold_articles": len(silver_rows) - len(pool),
        "gold_articles": sorted(gold_articles),
    }

def grouped_holdout(indices: Sequence[int], rows: Sequence[Dict[str, Any]],
                    frac: float = 0.2, seed: int = RANDOM_SEED
                    ) -> Tuple[List[int], List[int]]:
    by_article: Dict[str, List[int]] = defaultdict(list)
    for i in indices:
        by_article[str(rows[i].get("source_id", i))].append(i)
    aids = sorted(by_article)
    random.Random(seed).shuffle(aids)
    target = frac * len(indices)
    hold: List[int] = []
    for aid in aids:
        if len(hold) >= target:
            break
        hold.extend(by_article[aid])
    hold_set = set(hold)
    train = [i for i in indices if i not in hold_set]
    return train, sorted(hold)

def gold_cv_folds(gold_rows: Sequence[Dict[str, Any]], k: int = 5,
                  seed: int = RANDOM_SEED) -> List[Tuple[List[int], List[int]]]:
    by_article: Dict[str, List[int]] = defaultdict(list)
    for i, r in enumerate(gold_rows):
        by_article[str(r.get("source_id", i))].append(i)
    aids = sorted(by_article)
    random.Random(seed).shuffle(aids)
    folds: List[List[int]] = [[] for _ in range(k)]
    for i, aid in enumerate(aids):
        folds[i % k].extend(by_article[aid])
    out = []
    for i in range(k):
        test = sorted(folds[i])
        train = sorted(j for f in range(k) if f != i for j in folds[f])
        out.append((train, test))
    return out


def agreement_table(rows: Sequence[Dict[str, Any]], prefix_a: str, prefix_b: str
                    ) -> List[Dict[str, Any]]:
    shared = [r for r in rows
              if any(str(r.get(f"{prefix_a}_{lb}", "")).strip() for lb in LABEL_NAMES)
              and any(str(r.get(f"{prefix_b}_{lb}", "")).strip() for lb in LABEL_NAMES)]
    out: List[Dict[str, Any]] = []
    for lb in LABEL_NAMES:
        a = [str(r.get(f"{prefix_a}_{lb}", "")).upper() for r in shared]
        b = [str(r.get(f"{prefix_b}_{lb}", "")).upper() for r in shared]
        p = _pairs(a, b)
        out.append({
            "label": lb,
            "n": len(p),
            "raw_agreement": _r(raw_agreement(a, b)),
            "cohen_kappa": _r(cohen_kappa(a, b)),
            "pabak": _r(pabak(a, b)),
            "krippendorff_alpha": _r(krippendorff_alpha_nominal([
                [x or None for x in a], [y or None for y in b]])),
            "n_disagreements": sum(1 for x, y in p if x != y),
        })
    flat_a = [x or None for r in shared for x in
              (str(r.get(f"{prefix_a}_{lb}", "")).upper() for lb in LABEL_NAMES)]
    flat_b = [y or None for r in shared for y in
              (str(r.get(f"{prefix_b}_{lb}", "")).upper() for lb in LABEL_NAMES)]
    ks = [row["cohen_kappa"] for row in out if row["cohen_kappa"] is not None]
    out.append({"label": "OVERALL", "n": len(shared),
                "cohen_kappa": _r(sum(ks) / len(ks)) if ks else None,
                "krippendorff_alpha": _r(krippendorff_alpha_nominal([flat_a, flat_b]))})
    return out
