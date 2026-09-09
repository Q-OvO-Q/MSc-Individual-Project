from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import (CONDITIONAL_PROMPTS, DISPLAY_NAMES, LABEL_NAMES,
                     NOT_DETECTED, PRESENT)
from .rules import apply_rules

WORDING = {
    "specimen_named": ("the legend names a specific specimen or object",
                       "no specific specimen or object was named in the legend text"),
    "method_modality": ("the legend states an imaging method or modality",
                        "no imaging method or modality was detected in the legend text"),
    "scale_magnification": ("the legend gives scale or magnification information",
                            "no scale or magnification information was detected in the legend text"),
    "marker_stain_channel": ("the legend names a marker, stain or channel",
                             "no named marker, stain or channel was detected in the legend text"),
    "colour_channel_mapping": ("the legend links a colour or channel to what it shows",
                               "no explicit colour-to-content mapping was detected in the legend text"),
    "panel_position_mapping": ("the legend maps panels or positions to content",
                               "no panel-to-content mapping was detected in the legend text"),
    "visual_annotation_explanation": ("the legend explains a visual annotation",
                                      "no explanation of a visual annotation was detected in the legend text"),
}


@dataclass
class ElementReport:
    label: str
    display_name: str
    rule_decision: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    model_probability: Optional[float] = None
    model_decision: Optional[str] = None
    model_threshold: Optional[float] = None
    message: str = ""


@dataclass
class LegendReport:
    caption: str
    elements: List[ElementReport]
    prompts: List[Dict[str, str]]
    cues: Dict[str, bool]
    scale_subtype: str = ""
    disagreements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "caption": self.caption,
            "scale_evidence_subtype": self.scale_subtype,
            "cues": self.cues,
            "elements": [
                {"label": e.label,
                 "display_name": e.display_name,
                 "rule_decision": e.rule_decision,
                 "message": e.message,
                 "evidence": e.evidence,
                 "model_probability": e.model_probability,
                 "model_decision": e.model_decision,
                 "model_threshold": e.model_threshold}
                for e in self.elements
            ],
            "conditional_prompts": self.prompts,
            "model_rule_disagreements": self.disagreements,
        }


class LegendChecker:

    def __init__(self, model_path: Optional[Path] = None,
                 threshold: Optional[float] = None) -> None:
        self.model = None
        self.threshold = threshold
        if model_path and Path(model_path).exists():
            with Path(model_path).open("rb") as fh:
                self.model = pickle.load(fh)

    def _thresholds(self, n: int) -> List[float]:
        if self.threshold is not None:
            return [float(self.threshold)] * n
        tuned = getattr(self.model, "thresholds_", None)
        if tuned is not None and len(tuned) == n:
            return [float(t) for t in tuned]
        return [0.5] * n

    def check(self, caption: str) -> LegendReport:
        res = apply_rules(caption)
        probs = None
        if self.model is not None:
            probs = self.model.predict_proba([caption])[0]

        elements: List[ElementReport] = []
        disagreements: List[str] = []
        thresholds = self._thresholds(len(LABEL_NAMES))
        for j, label in enumerate(LABEL_NAMES):
            decision = res.labels[label]
            yes, no = WORDING[label]
            er = ElementReport(
                label=label,
                display_name=DISPLAY_NAMES[label],
                rule_decision=decision,
                evidence=res.spans(label)[:4],
                message=(yes if decision == PRESENT else no),
            )
            if probs is not None:
                p = float(probs[j])
                er.model_probability = round(p, 3)
                er.model_decision = PRESENT if p >= thresholds[j] else NOT_DETECTED
                er.model_threshold = round(thresholds[j], 3)
                if er.model_decision != decision:
                    disagreements.append(
                        f"{label}: rules say {decision.lower()}, the classifier "
                        f"says {er.model_decision.lower()} (p={p:.2f}). "
                        f"Treat this element as uncertain.")
            elements.append(er)

        return LegendReport(caption=caption, elements=elements,
                            prompts=self._prompts(res), cues=res.cues,
                            scale_subtype=res.subtypes.get("scale_magnification", ""),
                            disagreements=disagreements)

    def _prompts(self, res) -> List[Dict[str, str]]:
        L = res.labels
        cues = res.cues
        fired = {
            "marker_without_colour": (
                L["marker_stain_channel"] == PRESENT
                and L["colour_channel_mapping"] != PRESENT
                and cues["multi_marker_or_merge_cue"],
                "two or more markers (or a merge/overlay cue) with no colour mapping"),
            "symbol_without_explanation": (
                cues["symbol_cue"] and L["visual_annotation_explanation"] != PRESENT,
                "an annotation noun appears but is not explained"),
            "panel_cue_without_mapping": (
                cues["panel_cue"] and L["panel_position_mapping"] != PRESENT,
                "panel identifiers appear but are not mapped to content"),
            "micrograph_without_scale": (
                L["method_modality"] == PRESENT and L["scale_magnification"] != PRESENT,
                "an imaging modality is named but no scale information is given"),
            "image_without_specimen": (
                L["method_modality"] == PRESENT and L["specimen_named"] != PRESENT,
                "an imaging modality is named but no specific specimen is named"),
        }
        out: List[Dict[str, str]] = []
        for p in CONDITIONAL_PROMPTS:
            fire, trigger = fired[p["id"]]
            if fire:
                out.append({"id": p["id"], "trigger": trigger, "message": p["message"]})
        return out


TICK = {PRESENT: "[detected]", NOT_DETECTED: "[not detected]", "UNCLEAR": "[unclear]"}


def render_text(report: LegendReport, width: int = 96) -> str:
    lines: List[str] = []
    lines.append("=" * width)
    lines.append("MICROSCOPY LEGEND REPORTING-ELEMENT CHECK")
    lines.append("This tool reads legend TEXT only. It cannot see the figure, so it reports")
    lines.append("what the text does or does not say -- never what the image is missing.")
    lines.append("=" * width)
    for e in report.elements:
        lines.append(f"\n{TICK.get(e.rule_decision, '[?]'):16s} {e.display_name}")
        lines.append(f"    {e.message}.")
        for ev in e.evidence:
            lines.append(f"      evidence: \"{ev['text']}\"  "
                         f"(rule {ev['rule_id']}, chars {ev['start']}-{ev['end']})")
        if e.model_probability is not None:
            lines.append(f"      classifier: p(present) = {e.model_probability:.2f} "
                         f"at threshold {e.model_threshold:.2f} "
                         f"-> {e.model_decision.lower()}")
    if report.scale_subtype:
        lines.append(f"\nscale evidence subtype: {report.scale_subtype}")
    if report.disagreements:
        lines.append("\nUNCERTAIN ELEMENTS")
        for d in report.disagreements:
            lines.append(f"  - {d}")
    if report.prompts:
        lines.append("\nSUGGESTIONS (conditional -- they depend on what the figure contains)")
        for p in report.prompts:
            lines.append(f"  - trigger: {p['trigger']}")
            lines.append(f"    {p['message']}")
    else:
        lines.append("\nNo conditional suggestions were triggered.")
    lines.append("=" * width)
    return "\n".join(lines)
