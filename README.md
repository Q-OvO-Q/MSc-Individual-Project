Values are `PRESENT`, `NOT_DETECTED`, `UNCLEAR`.

## Pipeline

```bash
# 1. build a corpus: XML -> legends -> microscopy filter -> figure-type filter
#    -> deduplication -> rule pre-annotation (silver labels) -> selection dependence
python cli.py corpus --data data --source elife --n-articles 1500 --target-legends 900
python cli.py corpus --data data --source pmc --email you@example.org --n-articles 400
python cli.py corpus --data data --source local --xml-dir /path/to/jats
python cli.py validity --data data

# 2. draw a stratified pilot; writes a blind label sheet and a span sheet
python cli.py pilot --data data --n 300

# 3. ingest the filled sheets
python cli.py labels --data data --sheet a1_round1.csv \
    --retest a1_round2.csv --second a2.csv
python cli.py labels --data data --sheet a1_round1.csv \
    --retest a1_round2.csv --second a2.csv --adjudication adjudication_FILLED.csv

# 4. modelling ladder: two regimes, plus the locked held-out split
python cli.py train --data data --lock-test-split data/test_split.lock.json

# 5. error taxonomy and span-level evaluation
python cli.py errors --data data --span-sheet span_sheet_FILLED.csv

# 6. check a legend
python cli.py check --model data/models/hybrid_lr.pkl --text "Confocal images of ..."
```

### Selection dependence

Some inclusion cues are also label evidence ("scale bar" admits a caption and
counts as scale evidence), so for those elements the corpus is selected on the
outcome. For each element, every rule evidence span is blanked out with offsets
preserved and both inclusion gates — the lexical cue filter and the figure-type
classifier — are re-run on the masked text. Selection dependence is the share of
the corpus that would then fail, with the gate responsible. `corpus` runs this
at the end; `validity` runs it on an existing `corpus.jsonl`. Verdicts use
project thresholds: below 0.05 the prevalence is a reportable finding, 0.05 to
0.25 descriptive only, 0.25 and above not estimable.

### Label sets

`--sheet` is annotator 1's first pass and becomes `gold_*`. `--retest` is the same
annotator's second pass (`human2_*`, test-retest); `--second` is an independent
annotator (`human3_*`). `labels` reports Cohen's κ, PABAK and Krippendorff's α for
both comparisons, and writes an adjudication sheet for every disagreement between
`gold_*` and `human3_*`. Re-running with `--adjudication` produces `adj_*`, the
adjudicated benchmark; `train` and `errors` use it automatically when it exists
(`--label-set gold|adj` forces a choice).

### Evaluation

`train` runs regime A (train on silver labels, test on the benchmark) and regime B
(article-grouped 5-fold CV on the benchmark) over `majority`, `all_positive`,
`rules`, `tfidf_lr`, `tfidf_svm`, `lsa_lr`, `rulefeat_lr` and `hybrid_lr`, writing
per-label precision/recall/F1/MCC, macro and micro scores, bootstrap 95 % CIs and
exact McNemar tests against the rule baseline (Holm-corrected within each
model pair) to `data/results/`.

`--lock-test-split` cuts, or reuses, a fixed held-out split: 30 % of the benchmark
sampled by article, recorded with an order-independent fingerprint. Models are
trained on the remaining legends, with thresholds tuned on a grouped inner
holdout, and evaluated on the locked legends once.

`errors` builds out-of-fold predictions the same way regime B does, classifies
every error with a regex taxonomy, and reports each code's lift —
P(code | error) ÷ P(code | any evaluated legend) — so that codes describing common
phrasing are visible as such. With `--span-sheet` it also scores the detector's
character offsets against the human reference spans: partial-overlap precision and
recall, exact-boundary precision, mean IoU, and right-for-the-right-reason (the
share of label-level true positives whose span overlaps a human-marked span),
printed beside the median predicted span length.

`check` also takes `--file`, `--json`, and `--corpus <jsonl> --out <dir>` for batch
reports.

## Layout

```
mlc/config.py     label scheme, conditional prompts, seed
mlc/lexicons.py   every regex and word list
mlc/rules.py      the rule detectors and rule features
mlc/corpus.py     JATS extraction, collection, filters, pilot sampling, sheets
mlc/validity.py   selection dependence of each element on the inclusion rule
mlc/models.py     the modelling ladder
mlc/evaluate.py   metrics, bootstrap, McNemar, agreement, grouped splits, the lock
mlc/spans.py      span-level evaluation
mlc/errors.py     the error taxonomy
mlc/checker.py    the author-facing checker
cli.py            the pipeline steps
```

Seed `20260730` everywhere. Splits are grouped by article.
