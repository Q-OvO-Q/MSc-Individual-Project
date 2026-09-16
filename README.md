# Microscopy legend reporting-element checker

Detects textual evidence of seven reporting elements in microscopy figure legends.
It reads legend text only; it never inspects the image and never claims that
something is missing from a figure.

## Install

```bash
pip install -r requirements.txt
```

Python 3.9+.

## Elements

| label | question |
|---|---|
| `specimen_named` | does the legend name a specific material or object? |
| `method_modality` | does it state the imaging method or modality? |
| `scale_magnification` | does it give a scale bar, physical size, or magnification? |
| `marker_stain_channel` | does it name a dye, stain, fluorophore, reporter or channel? |
| `colour_channel_mapping` | is a colour explicitly linked to what it represents? |
| `panel_position_mapping` | are panel letters or positions mapped to content? |
| `visual_annotation_explanation` | are arrows, boxes, insets, asterisks explained? |

Values are `PRESENT`, `NOT_DETECTED`, `UNCLEAR`.

## Pipeline

```bash
# 1. build a corpus: XML -> legends -> microscopy filter -> figure-type filter
#    -> deduplication -> rule pre-annotation (silver labels)
python cli.py corpus --data data --source elife --n-articles 1500 --target-legends 900
python cli.py corpus --data data --source pmc --email you@example.org --n-articles 400
python cli.py corpus --data data --source local --xml-dir /path/to/jats

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
mlc/models.py     the modelling ladder
mlc/evaluate.py   metrics, bootstrap, McNemar, agreement, grouped splits, the lock
mlc/spans.py      span-level evaluation
mlc/errors.py     the error taxonomy
mlc/checker.py    the author-facing checker
cli.py            the six pipeline steps
```

Seed `20260730` everywhere. Splits are grouped by article.
