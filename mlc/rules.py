from __future__ import annotations

import hashlib
import re
from re import error
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from . import lexicons as LX
from .config import LABEL_NAMES, NOT_DETECTED, PRESENT, UNCLEAR

MASK_CHAR = "\x00"

_SENT_END = re.compile(r"[.;:!?]|\s—\s|\s-\s")

_DANGLING_PUNCT = re.compile(r"[,;:\-–—/(\[]\s*$")

_DANGLING_WORD = re.compile(
    r"\b(?:a|an|the|and|or|but|of|in|on|at|to|for|from|with|without|by|as|"
    r"into|onto|over|under|between|among|during|after|before|per|via|"
    r"is|are|was|were|be|been|being|has|have|had|that|which|whose|where|"
    r"when|while|than|then|both|either|neither|each|every|these|those|"
    r"this|its|their|our|his|her|using|used|shown|seen|created|generated|"
    r"indicated|described|performed|obtained|measured|according)\s*$",
    re.IGNORECASE)

_MIN_JUDGEABLE_CHARS = 25

@dataclass
class Evidence:
    label: str
    rule_id: str
    start: int
    end: int
    text: str
    context: str = ""

    def as_dict(self) -> Dict[str, object]:
        d: Dict[str, object] = {"rule_id": self.rule_id, "start": self.start,
                                "end": self.end, "text": self.text}
        if self.context:
            d["context"] = self.context
        return d

@dataclass
class RuleResult:
    labels: Dict[str, str] = field(default_factory=dict)
    evidence: Dict[str, List[Evidence]] = field(default_factory=dict)
    subtypes: Dict[str, str] = field(default_factory=dict)
    cues: Dict[str, bool] = field(default_factory=dict)

    def spans(self, label: str) -> List[Dict[str, object]]:
        return [e.as_dict() for e in self.evidence.get(label, [])]

    def evidence_text(self, label: str, limit: int = 3) -> str:
        seen: set = set()
        out: List[str] = []
        for e in self.evidence.get(label, []):
            t = " ".join(e.text.split())
            if t and t.lower() not in seen:
                seen.add(t.lower())
                out.append(t)
            if len(out) >= limit:
                break
        return " | ".join(out)

def _mask(text: str, spans: Sequence[Tuple[int, int]]) -> str:
    if not spans:
        return text
    chars = list(text)
    for s, e in spans:
        for i in range(max(0, s), min(len(chars), e)):
            chars[i] = MASK_CHAR
    return "".join(chars)

def _clean(s: str) -> str:
    return " ".join(s.replace(MASK_CHAR, " ").split())

def _sentence_tail(text: str, pos: int, max_len: int = 220) -> Tuple[str, int]:
    window = text[pos:pos + max_len]
    m = _SENT_END.search(window)
    end = m.start() if m else len(window)
    return window[:end], pos + end

def detect_specimen_named(raw: str) -> List[Evidence]:
    masked = _mask(raw, [m.span() for m in LX.ANTIBODY_HOST_TRAP.finditer(raw)])
    ev: List[Evidence] = []
    for m in LX.SPECIFIC_OBJECT.finditer(masked):
        ev.append(Evidence("specimen_named", "specific_object_lexicon",
                           m.start(), m.end(), raw[m.start():m.end()]))
        if len(ev) >= 8:
            break
    return ev

def detect_method_modality(raw: str) -> List[Evidence]:
    ev: List[Evidence] = []
    for m in LX.MODALITY_SAFE.finditer(raw):
        ev.append(Evidence("method_modality", "modality_lexicon",
                           m.start(), m.end(), m.group(0)))
        if len(ev) >= 6:
            break

    for m in LX.MODALITY_ACRONYM.finditer(raw):
        token = m.group(1)
        left = raw[max(0, m.start() - 18):m.start()]
        if LX.STAT_SEM_GUARD.search(left):
            continue
        window = raw[max(0, m.start() - 90):m.end() + 90]
        if token in {"SEM", "TEM", "STEM", "EM", "AFM"} and not LX.EM_CONTEXT.search(window):
            continue
        if token == "SIM" and not re.search(
                r"\b(?:structured|illumination|reconstruct\w*|microscop\w*|image)\b",
                window, LX.FLAGS):
            continue
        ev.append(Evidence("method_modality", f"acronym_{token}",
                           m.start(), m.end(), token))
    return ev

def detect_scale_magnification(raw: str) -> Tuple[List[Evidence], str]:
    ev: List[Evidence] = []
    subtypes: List[str] = []

    for m in LX.SCALE_BAR.finditer(raw):
        ev.append(Evidence("scale_magnification", "scale_bar",
                           m.start(), m.end(), m.group(0)))
        subtypes.append("scale_bar")

    for pat, rid in ((LX.LENGTH_VALUE_ABBREV, "unit_size_abbrev"),
                     (LX.LENGTH_VALUE_WORD, "unit_size_word")):
        for m in pat.finditer(raw):
            left = raw[max(0, m.start() - 40):m.start()]
            right = raw[m.end():m.end() + 12]
            if LX.WAVELENGTH_GUARD.search(left) or LX.WAVELENGTH_GUARD.search(right):
                continue
            if LX.CONCENTRATION_GUARD.search(left[-25:]):
                continue
            ev.append(Evidence("scale_magnification", rid,
                               m.start(), m.end(), m.group(0)))
            subtypes.append("unit_size")

    for pat, rid in ((LX.MAGNIFICATION, "magnification"),
                     (LX.OBJECTIVE_MAG, "objective_magnification")):
        for m in pat.finditer(raw):
            ev.append(Evidence("scale_magnification", rid,
                               m.start(), m.end(), m.group(0)))
            subtypes.append("magnification")

    for m in LX.BARE_MAG.finditer(raw):
        window = raw[max(0, m.start() - 30):m.end() + 25]
        if LX.BARE_MAG_GUARD.search(window):
            continue
        ev.append(Evidence("scale_magnification", "bare_magnification",
                           m.start(), m.end(), m.group(0)))
        subtypes.append("magnification")

    order = ["scale_bar", "unit_size", "magnification"]
    subtype = "+".join([s for s in order if s in subtypes])
    return ev, subtype

def detect_marker_stain_channel(raw: str) -> List[Evidence]:
    ev: List[Evidence] = []
    for pat, rid in (
        (LX.NAMED_MARKER, "named_marker"),
        (LX.FUSION_REPORTER, "fusion_reporter"),
        (LX.ANTIBODY, "antibody"),
        (LX.NAMED_CHANNEL, "named_channel"),
    ):
        for m in pat.finditer(raw):
            ev.append(Evidence("marker_stain_channel", rid,
                               m.start(), m.end(), m.group(0)))
            if len(ev) >= 12:
                return ev

    for m in LX.STAINED_FOR.finditer(raw):
        target = (m.group(1) or "").strip(" ,.;:")
        head = target.split()[0].lower() if target.split() else ""
        if not target or head in LX.STAINED_FOR_STOPWORDS:
            continue
        if len(head) < 2:
            continue
        ev.append(Evidence("marker_stain_channel", "stained_for_named_target",
                           m.start(1), m.end(1), target))
        if len(ev) >= 12:
            break
    return ev

_UNQUALIFYING = {
    "the", "a", "an", "this", "that", "these", "those", "its", "their", "our",
    "each", "every", "all", "both", "same", "other", "any", "some", "no",
    "and", "or", "of", "in", "on", "with", "for", "from", "to", "as", "by",
    "is", "are", "was", "were", "shown", "showing", "displayed", "indicated",
    "representative", "typical", "corresponding", "respective", "individual",
    "total", "overall", "strong", "weak", "positive", "negative",
    "red", "green", "blue", "cyan", "magenta", "yellow", "orange", "purple",
    "violet", "white", "black", "grey", "gray", "greyscale", "grayscale",
    "pink", "brown", "gold", "golden", "teal", "turquoise",
}

def _target_is_generic(m) -> bool:
    try:
        target = m.group("t")
    except (IndexError, error):
        return False
    if not target:
        return False
    word = target.strip(" ,.;:()").lower()
    if word not in LX.GENERIC_COLOUR_TARGET:
        return False
    try:
        before = m.string[max(0, m.start("t") - 40):m.start("t")]
    except (IndexError, error):
        return True
    prev = re.findall(r"[A-Za-z][\w./+-]*", before)
    if not prev:
        return True
    q = prev[-1].lower()
    if q in _UNQUALIFYING or q in LX.GENERIC_COLOUR_TARGET:
        return True
    return False

def detect_colour_channel_mapping(raw: str) -> List[Evidence]:
    masked = _mask(raw, [m.span() for m in LX.COLOUR_FIXED_NAMES.finditer(raw)])
    ev: List[Evidence] = []

    link = LX.MAP_LINK_VERB
    colour = LX.COLOUR_WORD
    patterns = [
        (re.compile(rf"(?P<t>{LX.MAPPING_TARGET.pattern[2:-2]})"
                    rf"\s*(?:\(|,\s*|:\s*|=\s*|—\s*|-\s*)\s*"
                    rf"(?P<c>{colour})\b", LX.FLAGS), "target_then_colour"),
        (re.compile(rf"\b(?P<c>{colour})\s*(?:=|:|,|—|-)?\s*"
                    rf"(?:{link})?\s*"
                    rf"(?:the\s+|a\s+|an\s+|this\s+|these\s+)?"
                    rf"(?P<t>{LX.MAPPING_TARGET.pattern[2:-2]})", LX.FLAGS),
         "colour_then_target"),
        (re.compile(rf"(?P<t>{LX.MAPPING_TARGET.pattern[2:-2]})"
                    rf"[^.;]{{0,28}}?\b(?:in|as|with|using)\s+(?P<c>{colour})\b",
                    LX.FLAGS), "target_in_colour"),
        (re.compile(rf"\b(?:pseudo-?colou?red|colou?r-?coded|colou?red|"
                    rf"rendered|displayed|merged)\s+(?:in\s+)?(?P<c>{colour})\b",
                    LX.FLAGS), "pseudocoloured"),
    ]
    for pat, rid in patterns:
        for m in pat.finditer(masked):
            if MASK_CHAR in m.group(0):
                continue
            gap = m.group(0)
            if len(gap) > 120:
                continue
            if _target_is_generic(m):
                continue
            ev.append(Evidence("colour_channel_mapping", rid,
                               m.start(), m.end(), _clean(m.group(0))))
            if len(ev) >= 10:
                return ev

    for pat, rid in ((LX.OPEN_TARGET_THEN_COLOUR, "open_target_then_colour"),
                     (LX.OPEN_TARGET_IN_COLOUR, "open_target_in_colour"),
                     (LX.OPEN_TARGET_COPULA_COLOUR, "open_target_copula_colour")):
        for m in pat.finditer(masked):
            if MASK_CHAR in m.group(0):
                continue
            target = (m.group("t") or "").strip(" ,.;:()").lower()
            if not target or target in LX._MAP_STOP_TARGET or target.isdigit():
                continue
            if _target_is_generic(m):
                continue
            if len(target) < 2:
                continue
            if re.fullmatch(LX.COLOUR_WORD, target, LX.FLAGS):
                continue
            ev.append(Evidence("colour_channel_mapping", rid,
                               m.start(), m.end(), _clean(m.group(0))))
            if len(ev) >= 10:
                return ev
    return ev

def _panel_candidates(raw: str) -> List[Tuple[int, int, str, str]]:
    out: List[Tuple[int, int, str, str]] = []
    for m in LX.PANEL_TOKEN.finditer(raw):
        tok = m.group("p1") or m.group("p2") or m.group("p3")
        if tok is None:
            continue
        out.append((m.start(), m.end(), tok, "panel_letter"))
    for m in LX.PANEL_RANGE.finditer(raw):
        out.append((m.start(), m.end(), m.group(0), "panel_range"))
    for m in LX.POSITION_WORD.finditer(raw):
        out.append((m.start(), m.end(), m.group(0), "position"))

    lower = [(m.start(), m.end(), m.group("pl")) for m in LX.PANEL_LOWER.finditer(raw)]
    letters = {c for _, _, tok in lower for c in re.findall(r"[a-z]", tok)}
    if len(letters) >= 2:
        for s0, e0, tok in lower:
            out.append((s0, e0, tok, "panel_letter_lower"))
    return sorted(out)

_THIN_CONTENT = re.compile(
    r"^\s*(?:and\s+|or\s+|the\s+|a\s+|an\s+)?"
    r"(?:representative|typical|example|examples|sample|samples|"
    r"quantification|quantitation|quantitative\s+analysis|analysis|"
    r"summary|statistics|data|results|as\s+in|same\s+as|see|"
    r"schematic|scheme|diagram|illustration|cartoon|model)"
    r"(?:\s+(?:of|for|from|in|the|a|an|this|these|those|its|their|"
    r"images?|panels?|plots?|graphs?|data|"
    r"results?|traces?|are|is|shown|showing))*\s*$", LX.FLAGS)

_TAIL_CONTINUES_SENTENCE = re.compile(
    r"^\s*(?:is|are|was|were|has|have|had|and|or|but|in|of|for|to|from|with|"
    r"shown|show|shows|as|also|therefore|which|that|then|both|respectively)\b",
    LX.FLAGS)

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{1,}")

def _has_content(fragment: str) -> bool:
    frag = fragment.strip()
    if len(frag) < 6:
        return False
    if _TAIL_CONTINUES_SENTENCE.match(frag) or _THIN_CONTENT.match(frag):
        return False
    if (LX.SPECIFIC_OBJECT.search(frag) or LX.MODALITY_SAFE.search(frag)
            or LX.NAMED_MARKER.search(frag) or LX.FUSION_REPORTER.search(frag)
            or LX.CONDITION_WORD.search(frag) or LX.COLOUR.search(frag)):
        return True
    return len(_WORD.findall(frag)) >= 3

def detect_panel_position_mapping(raw: str) -> List[Evidence]:
    ev: List[Evidence] = []
    for start, end, tok, kind in _panel_candidates(raw):
        left = raw[max(0, start - 30):start]
        if LX.CROSSREF_GUARD.search(left):
            continue
        tail, _ = _sentence_tail(raw, end)
        if kind in ("position", "panel_letter_lower"):
            tail = raw[end:end + 160]
            m = _SENT_END.search(tail)
            tail = tail[:m.start()] if m else tail
        if not _has_content(tail):
            continue
        ev.append(Evidence("panel_position_mapping", f"{kind}_with_content",
                           start, end, raw[start:end],
                           context=_clean(tail)[:160]))
        if len(ev) >= 8:
            break
    return ev

def detect_visual_annotation_explanation(raw: str) -> List[Evidence]:
    masked = _mask(raw, [m.span() for m in LX.ANNOTATION_TRAP.finditer(raw)])
    ev: List[Evidence] = []

    noun = LX.ANNOTATION_NOUN
    verb = LX.EXPLAIN_VERB
    patterns = [
        (re.compile(rf"\b(?:{noun})\s*(?:,|:)?\s*(?:{verb})\b[^.;]{{0,120}}\b",
                    LX.FLAGS), "noun_verb_content"),
        (re.compile(rf"\b(?:indicated|shown|marked|denoted|highlighted|"
                    rf"outlined|delineated|surrounded|labelled|labeled)\s+"
                    rf"(?:by|with|using)\s+(?:the\s+|a\s+|an\s+)?"
                    rf"(?:white|black|yellow|red|green|blue|cyan|magenta|"
                    rf"orange|dashed|dotted|solid|open|filled|closed)?\s*"
                    rf"(?:{noun})\b", LX.FLAGS), "indicated_by_noun"),
        (LX.MAGNIFY_INSTRUCTION, "magnified_region_instruction"),
        (re.compile(rf"\b(?:{noun})\s*(?:,|:|=)\s*"
                    rf"(?![Pp]\s*[<>=])[A-Za-z][^.;]{{3,100}}\b", LX.FLAGS),
         "noun_colon_content"),
    ]
    for pat, rid in patterns:
        for m in pat.finditer(masked):
            if MASK_CHAR in m.group(0):
                continue
            frag = _clean(m.group(0))
            if rid == "noun_colon_content" and not _has_content(frag):
                continue
            ev.append(Evidence("visual_annotation_explanation", rid,
                               m.start(), m.end(), frag[:160]))
            if len(ev) >= 8:
                return ev
    return ev

_MERGE_CUE = re.compile(r"\b(?:merge[ds]?|overlay|composite|co-?locali[sz]\w*|"
                        r"co-?stain\w*|dual|triple|multi-?colou?r)\b", LX.FLAGS)

def detect_cues(raw: str) -> Dict[str, bool]:
    markers = list(LX.NAMED_MARKER.finditer(raw)) + list(LX.FUSION_REPORTER.finditer(raw))
    distinct_markers = {m.group(0).lower() for m in markers}
    return {
        "panel_cue": bool(LX.PANEL_TOKEN.search(raw) or LX.PANEL_RANGE.search(raw)),
        "symbol_cue": bool(LX.ANNOTATION_TOKEN.search(
            _mask(raw, [m.span() for m in LX.ANNOTATION_TRAP.finditer(raw)]))),
        "colour_cue": bool(LX.COLOUR.search(
            _mask(raw, [m.span() for m in LX.COLOUR_FIXED_NAMES.finditer(raw)]))),
        "multi_marker_or_merge_cue": len(distinct_markers) >= 2 or bool(_MERGE_CUE.search(raw)),
        "looks_truncated": bool(_DANGLING_PUNCT.search(raw.strip())
                                or _DANGLING_WORD.search(raw.strip())),
    }

_DETECTORS = {
    "specimen_named": detect_specimen_named,
    "method_modality": detect_method_modality,
    "marker_stain_channel": detect_marker_stain_channel,
    "colour_channel_mapping": detect_colour_channel_mapping,
    "panel_position_mapping": detect_panel_position_mapping,
    "visual_annotation_explanation": detect_visual_annotation_explanation,
}

def apply_rules(caption: str, allow_unclear: bool = True) -> RuleResult:
    raw = " ".join((caption or "").split())
    res = RuleResult()
    res.cues = detect_cues(raw)

    too_short = len(raw) < _MIN_JUDGEABLE_CHARS
    fragmented = allow_unclear and (too_short or res.cues["looks_truncated"])

    for label, fn in _DETECTORS.items():
        ev = fn(raw)
        res.evidence[label] = ev
        if ev:
            res.labels[label] = PRESENT
        elif fragmented:
            res.labels[label] = UNCLEAR
        else:
            res.labels[label] = NOT_DETECTED

    ev, subtype = detect_scale_magnification(raw)
    res.evidence["scale_magnification"] = ev
    res.subtypes["scale_magnification"] = subtype
    if ev:
        res.labels["scale_magnification"] = PRESENT
    elif fragmented:
        res.labels["scale_magnification"] = UNCLEAR
    else:
        res.labels["scale_magnification"] = NOT_DETECTED

    res.labels = {k: res.labels[k] for k in LABEL_NAMES}
    _reconcile_evidence(res, raw)
    return res

def _reconcile_evidence(res: "RuleResult", raw: str) -> None:
    n = len(raw)
    for lb, items in res.evidence.items():
        fixed: List[Evidence] = []
        for e in items:
            s, t = int(e.start), int(e.end)
            if not (0 <= s < t <= n):
                continue
            fixed.append(Evidence(e.label, e.rule_id, s, t, raw[s:t], e.context)
                         if raw[s:t] != e.text else e)
        res.evidence[lb] = fixed

_FEATURE_CACHE: Dict[str, Tuple[Tuple[str, float], ...]] = {}

def _caption_key(caption: str) -> str:
    return hashlib.sha1(" ".join((caption or "").split())
                        .encode("utf-8", "ignore")).hexdigest()[:20]

def _rule_feature_items(caption: str) -> Tuple[Tuple[str, float], ...]:
    key = _caption_key(caption)
    hit = _FEATURE_CACHE.get(key)
    if hit is None:
        hit = tuple(sorted(_rule_feature_vector_uncached(caption).items()))
        _FEATURE_CACHE[key] = hit
    return hit

def rule_feature_vector(caption: str) -> Dict[str, float]:
    return dict(_rule_feature_items(caption))

def _rule_feature_vector_uncached(caption: str) -> Dict[str, float]:
    res = apply_rules(caption, allow_unclear=False)
    feats: Dict[str, float] = {}
    for label in LABEL_NAMES:
        n = len(res.evidence.get(label, []))
        feats[f"rule::{label}"] = 1.0 if n else 0.0
        feats[f"rulecount::{label}"] = float(min(n, 5))
    for cue, val in res.cues.items():
        feats[f"cue::{cue}"] = 1.0 if val else 0.0
    text = " ".join((caption or "").split())
    feats["meta::len_chars"] = min(len(text), 2000) / 2000.0
    feats["meta::n_sentences"] = min(text.count(". ") + 1, 20) / 20.0
    feats["meta::n_digits"] = min(sum(c.isdigit() for c in text), 40) / 40.0
    feats["meta::n_parens"] = min(text.count("("), 20) / 20.0
    return feats
