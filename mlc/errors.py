from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

from . import lexicons as LX
from .config import LABEL_NAMES, NOT_DETECTED, PRESENT
from .rules import apply_rules

TAXONOMY = [
    ("unlisted_modality_term",
     "modality named with a term outside the lexicon (tomogram, smFISH, "
     "single-molecule, photomicrograph, differential contrast, microscopically)",
     {"method_modality"}, "fn",
     re.compile(r"\b(?:tomogram|tomograph\w*|smFISH|single[- ]molecule|"
                r"photomicrograph\w*|differential\s+contrast|microscopic\w*|"
                r"CoSMoS|ratiometric|bioluminescen\w*|autoradiograph\w*)\b", LX.FLAGS)),
    ("non_spatial_scale_bar",
     "a 'scale bar' that is expressed in non-spatial units (pA, s, dF/F, nS)",
     {"scale_magnification"}, "fp",
     re.compile(r"scale\s?bars?[^.;]{0,40}(?:pA|mV|nS|pS|%|Hz|\bs\b|ms|"
                r"[Dd]F/F|a\.?u\.?)", LX.FLAGS)),
    ("colour_not_lexicalised",
     "colour mapping expressed without a bracket or copula the rules match "
     "('painted in', 'shown as', 'colors indicating', 'pseudocolor scale')",
     {"colour_channel_mapping"}, "fn",
     re.compile(r"\b(?:painted\s+in|shown\s+as|colou?rs?\s+indicat\w*|"
                r"pseudocolou?r|colou?r\s+gradient|shades\s+represent\w*|"
                r"colou?r-?coded|are\s+due\s+to)\b", LX.FLAGS)),
    ("annotation_without_verb",
     "an annotation is explained by apposition rather than by a verb "
     "('gaps (yellow arrows)', 'the target spine (arrowhead)')",
     {"visual_annotation_explanation"}, "fn",
     re.compile(rf"\((?:[a-z ]*)?(?:{LX.ANNOTATION_NOUN})\)", LX.FLAGS)),
    ("plot_symbol_key",
     "a graph-symbol key rather than an image annotation "
     "('circles, Parkin aggregation'; 'each symbol represents ...')",
     {"visual_annotation_explanation"}, "fn",
     re.compile(r"\b(?:circles?|squares?|diamonds?|triangles?|symbols?|"
                r"open\s+bars?|filled\s+bars?)\s*(?:,|:)?\s*"
                r"(?:represent\w*|indicat\w*|denote\w*|show\w*|are|is)\b", LX.FLAGS)),
    ("object_is_a_molecule",
     "the imaged object is a macromolecule or complex, not a cell or tissue "
     "(structural-biology figures)",
     {"specimen_named"}, "fn",
     re.compile(r"\b(?:cryo-?EM|crystal\s+structure|density\s+map|"
                r"atomic\s+model|ribbon|PDB|helix|helices|loop|residues?|"
                r"TM\d|domain)\b", LX.FLAGS)),
    ("panel_content_too_thin",
     "panel label followed by content the rules do not recognise as content "
     "('(A-D) Representative images')",
     {"panel_position_mapping"}, "fn",
     re.compile(r"\([A-Z](?:\s?[-–]\s?[A-Z])?\)\s*"
                r"(?i:representative|example|quantification|schematic|"
                r"illustration|summary|sample|diagram)\b", re.UNICODE)),
    ("marker_unnamed_or_paraphrased",
     "the visualised molecule is referred to indirectly "
     "('a fluorescent substrate', 'the indicated constructs', ISH targets)",
     {"marker_stain_channel"}, "fn",
     re.compile(r"\b(?:fluorescent\s+(?:substrate|reporter|sensor|protein)|"
                r"indicated\s+(?:constructs?|antibodies|probes?)|"
                r"in\s+situ\s+hybridi[sz]ation|probe\s+against|"
                r"expressing|transfected\s+with|tagged)\b", LX.FLAGS)),
    ("non_microscopy_figure",
     "the figure is not a micrograph at all (model schematic, gel, plot); "
     "a corpus-filter false positive",
     None, "any",
     re.compile(r"\b(?:flow\s?chart|schematic|diagram|model\s+based\s+on|"
                r"western\s+blot|2D\s+gel|EMSA|native\s+PAGE|raster\s+plot|"
                r"sample\s+traces|electrophysiolog\w*)\b", LX.FLAGS)),
    ("specimen_is_named_material",
     "the imaged specimen is a named engineered material (nanoparticle, "
     "hydrogel, doped oxide, scaffold, alloy), which the biological "
     "specimen lexicon cannot name (adjudication: named materials count)",
     {"specimen_named"}, "fn",
     re.compile(r"\b(?:nanoparticles?|nanospheres?|nanozymes?|nanocrystals?|"
                r"nanotubes?|quantum\s+dots?|hydrogels?|cryogels?|scaffolds?|"
                r"composites?|micelles?|liposomes?|microplates?|"
                r"stainless\s+steel|thin\s+films?|nanosheets?|aerogels?|"
                r"[A-Za-z]+-doped|doped\s+[A-Z])\b", LX.FLAGS)),
    ("marker_named_around_immuno_readout",
     "the antibody target is named around an immuno readout without a "
     "'stained for' verb ('IHC staining of E-cadherin', 'CD10 (+)', "
     "'co-expression of MPO and CitH3')",
     {"marker_stain_channel"}, "fn",
     re.compile(r"\b(?:IHC|immunohistochemi\w*|immunofluorescen\w*|"
                r"immunostain\w*)\s+(?:analys[ei]s\s+|image\w*\s+|"
                r"finding\w*\s+|staining\s+)?(?:of|for)\s+[A-Za-zα-ω]"
                r"|\bCD\d{1,3}\b|\(\s*[+−-]\s*\)", LX.FLAGS)),
    ("panel_letter_variant_not_lexicalised",
     "panel letters in a form the panel lexicon does not match: comma "
     "pairs '(A, B)', letter-colon 'A: ...', or inline lower-case 'a ... "
     "and b ...'",
     {"panel_position_mapping"}, "fn",
     re.compile(r"\([A-Za-z](?:\s?[,;]\s?[A-Za-z])+\)"
                r"|(?:^|[.;]\s)[A-H]:\s"
                r"|\b(?:and|or)\s[a-h]\s(?=[A-Z0-9])", re.UNICODE)),
    ("modality_adjective_form_missed",
     "the modality lexicon matches the noun (immunohistochemistry) but "
     "not the adjective (immunohistochemical), so adjective-only legends "
     "are missed",
     {"method_modality"}, "fn",
     re.compile(r"\bimmunohistochemical\b|\bimmunocytochemical\b|"
                r"\bhistopathologic\b", LX.FLAGS)),
    ("bracketed_magnification_vetoed",
     "a magnification token inside a bracket ('(IHC, x200)') is vetoed by "
     "the bare-magnification context guard when a word like 'cells' "
     "appears nearby",
     {"scale_magnification"}, "fn",
     re.compile(r"\([^()]{0,14}[×x]\s?\d{2,4}\s*\)", re.UNICODE)),
]

def classify_error(label: str, error_type: str, caption: str) -> List[str]:
    codes = []
    for code, _desc, labels, etype, probe in TAXONOMY:
        if labels is not None and label not in labels:
            continue
        if etype not in ("any", error_type):
            continue
        if probe.search(caption):
            codes.append(code)
    return codes or ["unclassified"]

def taxonomy_table() -> List[Dict[str, str]]:
    return [{"code": c, "description": d,
             "labels": ", ".join(sorted(l)) if l else "all",
             "error_type": t}
            for c, d, l, t, _ in TAXONOMY]

def collect_errors(rows: Sequence[Dict[str, Any]], predictions: Dict[str, Any],
                   model_name: str, gold_prefix: str = "gold",
                   max_chars: int = 400) -> List[Dict[str, Any]]:
    pred = predictions[model_name]
    out: List[Dict[str, Any]] = []
    for i, r in enumerate(rows):
        rule_res = apply_rules(r["caption"], allow_unclear=False)
        for j, lb in enumerate(LABEL_NAMES):
            g = str(r.get(f"{gold_prefix}_{lb}", "")).upper()
            if g not in (PRESENT, NOT_DETECTED):
                continue
            gp = g == PRESENT
            pp = bool(pred[i, j])
            if gp == pp:
                continue
            etype = "fn" if gp else "fp"
            codes = classify_error(lb, etype, r["caption"])
            out.append({
                "model": model_name, "legend_id": r["legend_id"],
                "source_id": r.get("source_id", ""),
                "label": lb, "error_type": etype,
                "gold": g, "predicted": PRESENT if pp else NOT_DETECTED,
                "error_codes": ", ".join(codes),
                "rule_evidence": rule_res.evidence_text(lb, limit=2),
                "annotator_note": r.get("annotator_note", ""),
                "n_chars": len(r["caption"]),
                "caption_excerpt": r["caption"][:max_chars],
            })
    return out

def error_summary(errors: Sequence[Dict[str, Any]],
                  all_rows: Optional[Sequence[Dict[str, Any]]] = None
                  ) -> List[Dict[str, Any]]:
    counter: Counter = Counter()
    for e in errors:
        for code in str(e["error_codes"]).split(", "):
            counter[(e["model"], e["label"], e["error_type"], code)] += 1

    base: Dict[str, float] = {}
    if all_rows:
        n = max(1, len(all_rows))
        for code, _d, _l, _t, probe in TAXONOMY:
            base[code] = sum(1 for r in all_rows
                             if probe.search(str(r.get("caption", "")))) / n

    per_model_label: Counter = Counter()
    for e in errors:
        per_model_label[(e["model"], e["label"], e["error_type"])] += 1

    rows = []
    for (m, lb, t, c), k in counter.most_common():
        denom = max(1, per_model_label[(m, lb, t)])
        rec: Dict[str, Any] = {"model": m, "label": lb, "error_type": t,
                               "error_code": c, "count": k,
                               "share_of_these_errors": round(k / denom, 4)}
        if c in base:
            rec["base_rate_in_evaluated_set"] = round(base[c], 4)
            rec["lift"] = (round((k / denom) / base[c], 2)
                           if base[c] > 0 else None)
        rows.append(rec)
    return rows

def complementarity(rows: Sequence[Dict[str, Any]], pred_a, pred_b,
                    name_a: str, name_b: str, gold_prefix: str = "gold"
                    ) -> List[Dict[str, Any]]:
    out = []
    for j, lb in enumerate(LABEL_NAMES):
        both = only_a = only_b = neither = 0
        for i, r in enumerate(rows):
            g = str(r.get(f"{gold_prefix}_{lb}", "")).upper()
            if g not in (PRESENT, NOT_DETECTED):
                continue
            t = g == PRESENT
            a = bool(pred_a[i, j]) == t
            b = bool(pred_b[i, j]) == t
            if a and b:
                both += 1
            elif a:
                only_a += 1
            elif b:
                only_b += 1
            else:
                neither += 1
        out.append({"label": lb, "both_right": both,
                    f"only_{name_a}_right": only_a,
                    f"only_{name_b}_right": only_b,
                    "both_wrong": neither,
                    "oracle_upper_bound_not_achievable": round(
                        (both + only_a + only_b) /
                        max(1, both + only_a + only_b + neither), 4),
                    "disagreement_rate": round(
                        (only_a + only_b) /
                        max(1, both + only_a + only_b + neither), 4)})
    return out
