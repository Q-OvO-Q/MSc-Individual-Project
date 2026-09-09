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

# 2. draw a stratified pilot and write a blind annotation sheet
python cli.py pilot --data data --n 300

# 3. ingest the filled sheet; a second sheet adds kappa / PABAK / Krippendorff alpha
python cli.py labels --data data --sheet pilot_filled.csv [--sheet2 pilot_filled_2.csv]

# 4. modelling ladder, two regimes, bootstrap CIs, McNemar
python cli.py train --data data

# 5. check a legend
python cli.py check --model data/models/hybrid_lr.pkl --text "Confocal images of ..."
```

`train` runs regime A (train on silver labels, test on the annotated pilot) and
regime B (article-grouped 5-fold CV on the annotated pilot) over
`majority`, `all_positive`, `rules`, `tfidf_lr`, `tfidf_svm`, `lsa_lr`,
`rulefeat_lr` and `hybrid_lr`, and writes per-label precision/recall/F1/MCC,
macro and micro scores, bootstrap 95 % CIs and exact McNemar tests against the
rule baseline to `data/results/`.

`check` also takes `--file`, `--json`, and `--corpus <jsonl> --out <dir>` for
batch reports.

## Layout

```
mlc/config.py     label scheme, conditional prompts, seed
mlc/lexicons.py   every regex and word list
mlc/rules.py      the rule detectors and rule features
mlc/corpus.py     JATS extraction, collection, filters, pilot sampling, sheets
mlc/models.py     the modelling ladder
mlc/evaluate.py   metrics, bootstrap, McNemar, agreement, grouped splits
mlc/checker.py    the author-facing checker
cli.py            the five pipeline steps
```

Seed `20260730` everywhere. Splits are grouped by article.
