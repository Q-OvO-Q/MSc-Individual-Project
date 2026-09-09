from __future__ import annotations

import argparse
import csv
import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np

from mlc import corpus as C
from mlc import evaluate as ev
from mlc.checker import LegendChecker, render_text
from mlc.config import LABEL_NAMES, PRESENT, RANDOM_SEED
from mlc.models import LADDER, build_model_zoo, tune_thresholds


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_csv(path: Path, rows: Sequence[Dict[str, Any]],
              fields: Sequence[str] = ()) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    keys = list(fields) or list(rows[0])
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})
    return path


def read_csv(path: Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def cmd_corpus(args) -> int:
    data = Path(args.data)
    if args.source == "pmc":
        raw = C.collect_pmc(data, target_articles=args.n_articles, email=args.email)
    elif args.source == "elife":
        articles = C.clone_elife_sample(Path(args.work_dir), n_articles=args.n_articles)
        raw = C.collect_elife(articles)
    else:
        raw = C.collect_local(Path(args.xml_dir))

    built = C.build_corpus(raw, per_article_cap=args.per_article_cap,
                           target_legends=args.target_legends)
    rows = C.annotate_corpus(built["corpus"])
    write_jsonl(data / "corpus.jsonl", rows)
    print(f"raw legends            {len(raw)}")
    print(f"dropped microscopy     {len(built['dropped_microscopy'])}")
    print(f"dropped figure type    {len(built['dropped_figure_type'])}")
    print(f"dropped dedupe         {len(built['dropped_dedupe'])}")
    print(f"corpus                 {len(rows)} legends / "
          f"{len({r['source_id'] for r in rows})} articles")
    for lb in LABEL_NAMES:
        n = sum(1 for r in rows if r[f"silver_{lb}"] == PRESENT)
        print(f"  silver PRESENT {lb:32s} {n / max(1, len(rows)):.3f}")
    return 0


def cmd_pilot(args) -> int:
    data = Path(args.data)
    rows = read_jsonl(data / "corpus.jsonl")
    chosen = C.stratified_pilot(rows, n_total=args.n, seed=args.seed,
                                max_per_article=args.max_per_article)
    write_csv(data / "pilot_blind.csv", C.blind_sheet(chosen))
    print(f"pilot {len(chosen)} legends -> {data / 'pilot_blind.csv'}")
    print("fill the manual_* columns with P / N / U, then run: labels")
    return 0


def cmd_labels(args) -> int:
    data = Path(args.data)
    rows = {r["legend_id"]: r for r in read_jsonl(data / "corpus.jsonl")}
    gold = C.parse_sheet(read_csv(Path(args.sheet)))
    out: List[Dict[str, Any]] = []
    for lid, vals in gold.items():
        if lid not in rows:
            continue
        rec = dict(rows[lid])
        for lb, v in vals.items():
            rec[f"gold_{lb}"] = v
        out.append(rec)

    if args.sheet2:
        second = C.parse_sheet(read_csv(Path(args.sheet2)))
        for rec in out:
            for lb, v in second.get(rec["legend_id"], {}).items():
                rec[f"gold2_{lb}"] = v
        table = ev.agreement_table(out, "gold", "gold2")
        write_csv(data / "results" / "agreement.csv", table)
        for r in table:
            print(f"{r['label']:32s} n={r['n']:4d} kappa={r['cohen_kappa']} "
                  f"pabak={r.get('pabak')} alpha={r['krippendorff_alpha']}")

    write_jsonl(data / "pilot_labelled.jsonl", out)
    print(f"{len(out)} labelled legends -> {data / 'pilot_labelled.jsonl'}")
    return 0


def _mcnemar_table(y_true, mask, preds: Dict[str, Any], reference: str = "rules"
                   ) -> List[Dict[str, Any]]:
    rows, pvals = [], []
    for name, p in preds.items():
        if name == reference:
            continue
        for j, lb in enumerate(LABEL_NAMES):
            m = ev.mcnemar(y_true, preds[reference], p, mask, j)
            rows.append({"model_a": reference, "model_b": name, "label": lb, **m})
            pvals.append(m["p_value"])
    for r, adj in zip(rows, ev.holm_bonferroni(pvals)):
        r["p_holm"] = adj
    return rows


def _report(title: str, summary: List[Dict[str, Any]]) -> None:
    print(f"\n{title}")
    print(f"{'model':16s} {'macroF1':>8s} {'95% CI':>16s} {'microF1':>8s} "
          f"{'macroMCC':>9s} {'macroP':>7s} {'macroR':>7s}")
    for r in summary:
        print(f"{r['model']:16s} {r['macro_f1']:8.3f} {r['macro_f1_ci95']:>16s} "
              f"{r['micro_f1']:8.3f} {str(r['macro_mcc']):>9s} "
              f"{r['macro_precision']:7.3f} {r['macro_recall']:7.3f}")


def cmd_train(args) -> int:
    data = Path(args.data)
    res_dir = data / "results"
    silver = read_jsonl(data / "corpus.jsonl")
    gold = read_jsonl(data / "pilot_labelled.jsonl")
    gold = [r for r in gold
            if any(str(r.get(f"gold_{lb}", "")).strip() for lb in LABEL_NAMES)]

    splits = ev.build_splits(silver, gold, seed=args.seed)
    tr, dv, te = splits["silver_train"], splits["silver_dev"], splits["gold_test"]
    Xtr = [r["caption"] for r in tr]
    Xdv = [r["caption"] for r in dv]
    Xte = [r["caption"] for r in te]
    Ytr, Mtr = (np.array(a) for a in ev.binary_targets(tr, "silver"))
    Ydv, Mdv = (np.array(a) for a in ev.binary_targets(dv, "silver"))
    Yte, Mte = (np.array(a) for a in ev.binary_targets(te, "gold"))
    print(f"silver_train={len(tr)}  silver_dev={len(dv)}  gold_test={len(te)}")

    per_label: List[Dict[str, Any]] = []

    zoo = build_model_zoo()
    tuned: Dict[str, Any] = {}
    for name, mdl in zoo.items():
        if not hasattr(mdl, "set_thresholds"):
            continue
        mdl.fit(Xtr, Ytr, Mtr)
        th = tune_thresholds(mdl, Xdv, Ydv, Mdv)
        tuned[name] = th.tolist()
        mdl.set_thresholds(th)

    results, boots, preds = {}, {}, {}
    for name, model in zoo.items():
        if name not in tuned:
            model.fit(Xtr, Ytr, Mtr)
        p = model.predict(Xte)
        preds[name] = p
        results[name] = ev.evaluate(Yte, p, Mte)
        boots[name] = ev.bootstrap_macro_f1(Yte, p, Mte, n_boot=args.n_boot,
                                            seed=args.seed)
        per_label += ev.metrics_to_rows(name, "regime_a", results[name])
        print(f"[regime a] {name:14s} macroF1={results[name]['macro_f1']:.3f}",
              flush=True)

    summary_a = ev.summary_table(results, boots)
    write_csv(res_dir / "model_summary_regime_a.csv", summary_a)
    write_csv(res_dir / "mcnemar_regime_a.csv", _mcnemar_table(Yte, Mte, preds))
    _report("REGIME A -- train on silver labels, test on the annotated pilot",
            summary_a)

    (data / "models").mkdir(parents=True, exist_ok=True)
    for name in ("rules", "hybrid_lr", "rulefeat_lr", "tfidf_lr"):
        with (data / "models" / f"{name}.pkl").open("wb") as fh:
            pickle.dump(zoo[name], fh)

    folds = ev.gold_cv_folds(te, k=args.cv_folds, seed=args.seed)
    cv_summary, cv_preds, cv_boots, cv_results = [], {}, {}, {}
    for name in LADDER:
        oof = np.zeros_like(Yte)
        for train_idx, test_idx in folds:
            mdl = build_model_zoo()[name]
            if hasattr(mdl, "set_thresholds") and len(train_idx) >= 25:
                inner_tr, inner_dv = ev.grouped_holdout(train_idx, te, frac=0.2,
                                                        seed=args.seed)
                if not inner_dv or not inner_tr:
                    inner_tr, inner_dv = train_idx, train_idx
                mdl.fit([Xte[i] for i in inner_tr], Yte[inner_tr], Mte[inner_tr])
                th = tune_thresholds(mdl, [Xte[i] for i in inner_dv],
                                     Yte[inner_dv], Mte[inner_dv])
                mdl.fit([Xte[i] for i in train_idx], Yte[train_idx], Mte[train_idx])
                mdl.set_thresholds(th)
            else:
                mdl.fit([Xte[i] for i in train_idx], Yte[train_idx], Mte[train_idx])
            oof[test_idx] = mdl.predict([Xte[i] for i in test_idx])
        cv_preds[name] = oof
        cv_results[name] = ev.evaluate(Yte, oof, Mte)
        cv_boots[name] = ev.bootstrap_macro_f1(Yte, oof, Mte, n_boot=args.n_boot,
                                               seed=args.seed)
        per_label += ev.metrics_to_rows(name, f"regime_b_{args.cv_folds}foldCV",
                                        cv_results[name])
        print(f"[regime b] {name:14s} macroF1={cv_results[name]['macro_f1']:.3f}",
              flush=True)

    cv_summary = ev.summary_table(cv_results, cv_boots)
    write_csv(res_dir / "model_summary_regime_b.csv", cv_summary)
    write_csv(res_dir / "mcnemar_regime_b.csv", _mcnemar_table(Yte, Mte, cv_preds))
    write_csv(res_dir / "metrics_per_label.csv", per_label,
              ["model", "split", "label", "support", "n", "tp", "fp", "fn", "tn",
               "precision", "recall", "f1", "mcc", "accuracy"])
    _report(f"REGIME B -- article-grouped {args.cv_folds}-fold CV on the "
            f"annotated pilot", cv_summary)
    print(f"\nwritten to {res_dir}")
    return 0


def cmd_check(args) -> int:
    checker = LegendChecker(Path(args.model) if args.model else None,
                            threshold=args.threshold)
    if args.corpus:
        rows = read_jsonl(Path(args.corpus))[:args.limit]
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for r in rows:
            report = checker.check(r["caption"])
            (out / f"{r['legend_id']}.txt").write_text(render_text(report),
                                                       encoding="utf-8")
        print(f"{len(rows)} reports -> {out}")
        return 0

    text = Path(args.file).read_text(encoding="utf-8") if args.file else args.text
    report = checker.check(text)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
          if args.json else render_text(report))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cli.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("corpus")
    p.add_argument("--data", default="data")
    p.add_argument("--source", choices=["elife", "pmc", "local"], default="elife")
    p.add_argument("--work-dir", default=".cache")
    p.add_argument("--xml-dir", default="")
    p.add_argument("--email", default="")
    p.add_argument("--n-articles", type=int, default=1500)
    p.add_argument("--target-legends", type=int, default=900)
    p.add_argument("--per-article-cap", type=int, default=3)
    p.set_defaults(func=cmd_corpus)

    p = sub.add_parser("pilot")
    p.add_argument("--data", default="data")
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--max-per-article", type=int, default=2)
    p.add_argument("--seed", type=int, default=RANDOM_SEED)
    p.set_defaults(func=cmd_pilot)

    p = sub.add_parser("labels")
    p.add_argument("--data", default="data")
    p.add_argument("--sheet", required=True)
    p.add_argument("--sheet2", default="")
    p.set_defaults(func=cmd_labels)

    p = sub.add_parser("train")
    p.add_argument("--data", default="data")
    p.add_argument("--n-boot", type=int, default=2000)
    p.add_argument("--cv-folds", type=int, default=5)
    p.add_argument("--seed", type=int, default=RANDOM_SEED)
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("check")
    p.add_argument("--model", default="")
    p.add_argument("--text", default="")
    p.add_argument("--file", default="")
    p.add_argument("--corpus", default="")
    p.add_argument("--out", default="reports")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--threshold", type=float, default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_check)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
