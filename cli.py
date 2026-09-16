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
from mlc import errors as E
from mlc import evaluate as ev
from mlc import spans as SP
from mlc.checker import LegendChecker, render_text
from mlc.config import LABEL_NAMES, PRESENT, RANDOM_SEED
from mlc.models import LADDER, build_model_zoo, tune_thresholds

ANNOTATOR_PREFIX = {"sheet": "gold", "retest": "human2", "second": "human3"}


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


def resolve_label_set(rows: Sequence[Dict[str, Any]], requested: str) -> str:
    if requested != "auto":
        return requested
    for prefix in ("adj", "gold"):
        if any(str(r.get(f"{prefix}_{lb}", "")).strip()
               for r in rows for lb in LABEL_NAMES):
            return prefix
    return "gold"


def labelled_rows(data: Path, label_set: str):
    rows = read_jsonl(data / "pilot_labelled.jsonl")
    key = resolve_label_set(rows, label_set)
    rows = [r for r in rows
            if any(str(r.get(f"{key}_{lb}", "")).strip() for lb in LABEL_NAMES)]
    return rows, key


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
    write_csv(data / "span_sheet_TO_FILL.csv", SP.span_sheet(chosen))
    print(f"pilot {len(chosen)} legends")
    print(f"  label sheet  {data / 'pilot_blind.csv'}   fill manual_* with P / N / U")
    print(f"  span sheet   {data / 'span_sheet_TO_FILL.csv'}   paste the exact "
          f"phrases that justify each PRESENT, separated by |")
    return 0


def cmd_labels(args) -> int:
    data = Path(args.data)
    rows = {r["legend_id"]: dict(r) for r in read_jsonl(data / "corpus.jsonl")}
    ingested: List[str] = []
    order: List[str] = []
    for flag, prefix in ANNOTATOR_PREFIX.items():
        path = getattr(args, flag)
        if not path:
            continue
        for lid, vals in C.parse_sheet(read_csv(Path(path))).items():
            if lid not in rows:
                continue
            if prefix == "gold":
                order.append(lid)
            for lb, v in vals.items():
                rows[lid][f"{prefix}_{lb}"] = v
        ingested.append(prefix)
    out = [rows[lid] for lid in order]
    print(f"ingested label sets: {', '.join(ingested)}  ({len(out)} legends)")

    table: List[Dict[str, Any]] = []
    for prefix, name in (("human3", "inter-annotator: A1 vs A2"),
                         ("human2", "intra-annotator: A1 round 1 vs round 2")):
        if prefix not in ingested:
            continue
        for r in ev.agreement_table(out, "gold", prefix):
            table.append({"comparison": name, **r})
    if table:
        write_csv(data / "results" / "agreement.csv", table)
        for r in table:
            print(f"  {r['comparison'][:24]:24s} {r['label']:32s} "
                  f"n={r['n']:4d} kappa={r['cohen_kappa']} pabak={r.get('pabak')} "
                  f"alpha={r['krippendorff_alpha']}")

    if args.adjudication:
        out, n = C.apply_adjudication(out, read_csv(Path(args.adjudication)), "gold")
        print(f"adjudication applied: {n} overridden judgements -> adj_*")
    elif "human3" in ingested:
        sheet = C.adjudication_sheet(out, "gold", "human3")
        write_csv(data / "adjudication_TO_FILL.csv", sheet)
        print(f"{len(sheet)} disagreement(s) -> {data / 'adjudication_TO_FILL.csv'}; "
              f"fill the adjudicated column and re-run with --adjudication")

    write_jsonl(data / "pilot_labelled.jsonl", out)
    print(f"written {data / 'pilot_labelled.jsonl'}")
    return 0


def _mcnemar_table(y_true, mask, preds: Dict[str, Any], reference: str = "rules"
                   ) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for name, p in preds.items():
        if name == reference:
            continue
        family = [{"model_a": reference, "model_b": name, "label": lb,
                   **ev.mcnemar(y_true, preds[reference], p, mask, j)}
                  for j, lb in enumerate(LABEL_NAMES)]
        adjusted = ev.holm_bonferroni([r["p_value"] for r in family])
        for r, adj in zip(family, adjusted):
            r["p_holm"] = adj
            r["family_size"] = len(family)
        rows += family
    return rows


def _report(title: str, summary: List[Dict[str, Any]]) -> None:
    print(f"\n{title}")
    print(f"{'model':16s} {'macroF1':>8s} {'95% CI':>16s} {'microF1':>8s} "
          f"{'macroMCC':>9s} {'macroP':>7s} {'macroR':>7s}")
    for r in summary:
        print(f"{r['model']:16s} {r['macro_f1']:8.3f} {r['macro_f1_ci95']:>16s} "
              f"{r['micro_f1']:8.3f} {str(r['macro_mcc']):>9s} "
              f"{r['macro_precision']:7.3f} {r['macro_recall']:7.3f}")


def _fit_cv(name, X, Y, M, rows, folds, seed):
    oof = np.zeros_like(Y)
    for train_idx, test_idx in folds:
        mdl = build_model_zoo()[name]
        if hasattr(mdl, "set_thresholds") and len(train_idx) >= 25:
            inner_tr, inner_dv = ev.grouped_holdout(train_idx, rows, frac=0.2,
                                                    seed=seed)
            if not inner_dv or not inner_tr:
                inner_tr, inner_dv = train_idx, train_idx
            mdl.fit([X[i] for i in inner_tr], Y[inner_tr], M[inner_tr])
            th = tune_thresholds(mdl, [X[i] for i in inner_dv],
                                 Y[inner_dv], M[inner_dv])
            mdl.fit([X[i] for i in train_idx], Y[train_idx], M[train_idx])
            mdl.set_thresholds(th)
        else:
            mdl.fit([X[i] for i in train_idx], Y[train_idx], M[train_idx])
        oof[test_idx] = mdl.predict([X[i] for i in test_idx])
    return oof


def cmd_train(args) -> int:
    data = Path(args.data)
    res_dir = data / "results"
    silver = read_jsonl(data / "corpus.jsonl")
    gold, lkey = labelled_rows(data, args.label_set)
    print(f"label set: {lkey}_*  ({len(gold)} annotated legends)")

    splits = ev.build_splits(silver, gold, seed=args.seed)
    tr, dv, te = splits["silver_train"], splits["silver_dev"], splits["gold_test"]
    Xtr = [r["caption"] for r in tr]
    Xdv = [r["caption"] for r in dv]
    Xte = [r["caption"] for r in te]
    Ytr, Mtr = (np.array(a) for a in ev.binary_targets(tr, "silver"))
    Ydv, Mdv = (np.array(a) for a in ev.binary_targets(dv, "silver"))
    Yte, Mte = (np.array(a) for a in ev.binary_targets(te, lkey))
    print(f"silver_train={len(tr)}  silver_dev={len(dv)}  benchmark={len(te)}")

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
    write_csv(res_dir / f"model_summary_regime_a_{lkey}.csv", summary_a)
    write_csv(res_dir / f"mcnemar_regime_a_{lkey}.csv",
              _mcnemar_table(Yte, Mte, preds))
    _report("REGIME A -- train on silver labels, test on the annotated benchmark",
            summary_a)

    (data / "models").mkdir(parents=True, exist_ok=True)
    for name in ("rules", "hybrid_lr", "rulefeat_lr", "tfidf_lr"):
        with (data / "models" / f"{name}.pkl").open("wb") as fh:
            pickle.dump(zoo[name], fh)

    folds = ev.gold_cv_folds(te, k=args.cv_folds, seed=args.seed)
    cv_preds, cv_boots, cv_results = {}, {}, {}
    for name in LADDER:
        oof = _fit_cv(name, Xte, Yte, Mte, te, folds, args.seed)
        cv_preds[name] = oof
        cv_results[name] = ev.evaluate(Yte, oof, Mte)
        cv_boots[name] = ev.bootstrap_macro_f1(Yte, oof, Mte, n_boot=args.n_boot,
                                               seed=args.seed)
        per_label += ev.metrics_to_rows(name, f"regime_b_{args.cv_folds}foldCV",
                                        cv_results[name])
        print(f"[regime b] {name:14s} macroF1={cv_results[name]['macro_f1']:.3f}",
              flush=True)

    cv_summary = ev.summary_table(cv_results, cv_boots)
    write_csv(res_dir / f"model_summary_regime_b_{lkey}.csv", cv_summary)
    write_csv(res_dir / f"mcnemar_regime_b_{lkey}.csv",
              _mcnemar_table(Yte, Mte, cv_preds))
    _report(f"REGIME B -- article-grouped {args.cv_folds}-fold CV on the "
            f"annotated benchmark", cv_summary)

    if args.lock_test_split:
        lock = ev.lock_test_split(te, Path(args.lock_test_split),
                                  test_fraction=args.test_fraction, seed=args.seed)
        parts = ev.apply_lock(te, lock)
        dev_rows, test_rows = parts["devpool"], parts["test"]
        Xd = [r["caption"] for r in dev_rows]
        Xt = [r["caption"] for r in test_rows]
        Yd, Md = (np.array(a) for a in ev.binary_targets(dev_rows, lkey))
        Yt, Mt = (np.array(a) for a in ev.binary_targets(test_rows, lkey))
        locked_summary = []
        for name in LADDER:
            mdl = build_model_zoo()[name]
            mdl.fit(Xd, Yd, Md)
            if hasattr(mdl, "set_thresholds"):
                itr, idv = ev.grouped_holdout(list(range(len(dev_rows))), dev_rows,
                                              frac=0.2, seed=args.seed)
                if idv:
                    inner = build_model_zoo()[name]
                    inner.fit([Xd[i] for i in itr], Yd[itr], Md[itr])
                    mdl.set_thresholds(tune_thresholds(
                        inner, [Xd[i] for i in idv], Yd[idv], Md[idv]))
            pr = mdl.predict(Xt)
            r = ev.evaluate(Yt, pr, Mt)
            b = ev.bootstrap_macro_f1(Yt, pr, Mt, n_boot=args.n_boot, seed=args.seed)
            per_label += ev.metrics_to_rows(name, "locked_test", r)
            locked_summary.append({
                "model": name, "macro_f1": r["macro_f1"],
                "macro_f1_ci95": f"[{b['ci95_low']}, {b['ci95_high']}]",
                "macro_mcc": r["macro_mcc"], "micro_f1": r["micro_f1"],
                "n_test": len(test_rows)})
            print(f"[locked]   {name:14s} macroF1={r['macro_f1']:.3f}", flush=True)
        locked_summary.sort(key=lambda x: -x["macro_f1"])
        write_csv(res_dir / f"model_summary_locked_test_{lkey}.csv", locked_summary)
        print(f"\nLOCKED TEST SPLIT  devpool={len(dev_rows)}  "
              f"test={len(test_rows)} legends / {lock['n_test_articles']} articles"
              f"  fingerprint={lock['fingerprint']}  reused={lock['reused']}")
        print(f"{'model':16s} {'macroF1':>8s} {'95% CI':>16s} {'macroMCC':>9s}")
        for r in locked_summary:
            print(f"{r['model']:16s} {r['macro_f1']:8.3f} "
                  f"{r['macro_f1_ci95']:>16s} {str(r['macro_mcc']):>9s}")

    write_csv(res_dir / f"metrics_per_label_{lkey}.csv", per_label,
              ["model", "split", "label", "support", "n", "tp", "fp", "fn", "tn",
               "precision", "recall", "f1", "mcc", "accuracy"])
    print(f"\nwritten to {res_dir}")
    return 0


def cmd_errors(args) -> int:
    data = Path(args.data)
    res_dir = data / "results"
    gold, lkey = labelled_rows(data, args.label_set)
    X = [r["caption"] for r in gold]
    Y, M = (np.array(a) for a in ev.binary_targets(gold, lkey))
    folds = ev.gold_cv_folds(gold, k=args.cv_folds, seed=args.seed)
    preds = {name: _fit_cv(name, X, Y, M, gold, folds, args.seed)
             for name in ("rules", "tfidf_lr", "hybrid_lr")}

    write_csv(res_dir / "error_taxonomy.csv", E.taxonomy_table())
    all_err: List[Dict[str, Any]] = []
    for name in preds:
        all_err += E.collect_errors(gold, preds, name, gold_prefix=lkey)
    write_csv(res_dir / "errors_detail.csv", all_err,
              ["model", "label", "error_type", "error_codes", "gold", "predicted",
               "legend_id", "source_id", "n_chars", "rule_evidence",
               "annotator_note", "caption_excerpt"])
    write_csv(res_dir / "errors_summary.csv", E.error_summary(all_err, gold))
    write_csv(res_dir / "complementarity_rules_vs_tfidf.csv",
              E.complementarity(gold, preds["rules"], preds["tfidf_lr"],
                                "rules", "tfidf", gold_prefix=lkey))
    n_rule = sum(1 for e in all_err if e["model"] == "rules")
    fn = sum(1 for e in all_err if e["model"] == "rules" and e["error_type"] == "fn")
    print(f"rule-baseline errors on the benchmark: {n_rule} "
          f"({fn} misses, {n_rule - fn} false alarms)")

    if args.span_sheet:
        sheet = read_csv(Path(args.span_sheet))
        caps = {r["legend_id"]: r["caption"] for r in gold}
        refs = SP.reference_spans_from_sheet(sheet, caps)
        sres = SP.evaluate_spans(gold, refs, lkey)
        write_csv(res_dir / "span_metrics.csv", SP.to_rows(sres))
        print(f"\nSPAN EVALUATION against "
              f"{sum(sres['per_label'][lb]['n_reference_spans'] for lb in LABEL_NAMES)}"
              f" human reference spans")
        print(f"{'element':32s} {'ref':>6s} {'partP':>7s} {'partR':>7s} "
              f"{'exactP':>7s} {'IoU':>6s} {'RFRR':>6s} {'medch':>6s}")
        for lb in LABEL_NAMES:
            r = sres["per_label"][lb]
            print(f"{lb:32s} {r['n_reference_spans']:6d} "
                  f"{str(r['span_precision_partial']):>7s} "
                  f"{str(r['span_recall_partial']):>7s} "
                  f"{str(r['span_precision_exact']):>7s} "
                  f"{str(r['mean_iou_of_matches']):>6s} "
                  f"{str(r['right_for_the_right_reason']):>6s} "
                  f"{str(r['median_pred_span_chars']):>6s}")
        m = sres["macro"]
        print(f"{'MACRO':32s} {'':>6s} {m['span_precision_partial']:>7} "
              f"{m['span_recall_partial']:>7} {'':>7} {'':>6} "
              f"{m['right_for_the_right_reason']:>6}")
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
    p.add_argument("--sheet", required=True,
                   help="annotator 1, round 1 -> gold_*")
    p.add_argument("--retest", default="",
                   help="annotator 1, round 2 -> human2_*, intra-annotator")
    p.add_argument("--second", default="",
                   help="annotator 2 -> human3_*, inter-annotator")
    p.add_argument("--adjudication", default="",
                   help="filled adjudication sheet -> adj_*")
    p.set_defaults(func=cmd_labels)

    p = sub.add_parser("train")
    p.add_argument("--data", default="data")
    p.add_argument("--label-set", choices=["auto", "gold", "adj"], default="auto")
    p.add_argument("--lock-test-split", default="")
    p.add_argument("--test-fraction", type=float, default=0.30)
    p.add_argument("--n-boot", type=int, default=2000)
    p.add_argument("--cv-folds", type=int, default=5)
    p.add_argument("--seed", type=int, default=RANDOM_SEED)
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("errors")
    p.add_argument("--data", default="data")
    p.add_argument("--label-set", choices=["auto", "gold", "adj"], default="auto")
    p.add_argument("--span-sheet", default="")
    p.add_argument("--cv-folds", type=int, default=5)
    p.add_argument("--seed", type=int, default=RANDOM_SEED)
    p.set_defaults(func=cmd_errors)

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
