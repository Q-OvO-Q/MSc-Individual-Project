from __future__ import annotations

from typing import Dict, List

PRESENT = "PRESENT"
NOT_DETECTED = "NOT_DETECTED"
UNCLEAR = "UNCLEAR"

LABEL_NAMES: List[str] = [
    "specimen_named",
    "method_modality",
    "scale_magnification",
    "marker_stain_channel",
    "colour_channel_mapping",
    "panel_position_mapping",
    "visual_annotation_explanation",
]

DISPLAY_NAMES: Dict[str, str] = {
    "specimen_named": "Named specimen / object evidence",
    "method_modality": "Imaging method / modality evidence",
    "scale_magnification": "Scale / magnification evidence",
    "marker_stain_channel": "Marker / stain / channel term evidence",
    "colour_channel_mapping": "Colour-channel mapping evidence",
    "panel_position_mapping": "Panel / position mapping evidence",
    "visual_annotation_explanation": "Visual annotation explanation evidence",
}

CONDITIONAL_PROMPTS = [
    {
        "id": "marker_without_colour",
        "message": (
            "Marker or stain terms were detected, but no explicit colour-channel "
            "mapping was found. If the figure is multicolour, consider stating which "
            "colour corresponds to each marker."
        ),
    },
    {
        "id": "symbol_without_explanation",
        "message": (
            "A visual-annotation term (for example arrow, asterisk, box or inset) was "
            "detected without an explanation of what it marks. If these annotations "
            "appear in the image, consider explaining them in the legend."
        ),
    },
    {
        "id": "panel_cue_without_mapping",
        "message": (
            "Panel identifiers were detected but no panel-to-content mapping was found "
            "in the legend text. If the figure has multiple panels, consider stating "
            "what each panel shows."
        ),
    },
    {
        "id": "micrograph_without_scale",
        "message": (
            "No scale-bar or magnification information was detected in the legend text. "
            "If the image contains a scale bar, consider stating its length in the "
            "legend."
        ),
    },
    {
        "id": "image_without_specimen",
        "message": (
            "An imaging modality was detected but the legend does not name a specific "
            "specimen or object. Consider naming the sample explicitly in the legend."
        ),
    },
]

MIN_CAPTION_CHARS = 40
MAX_CAPTION_CHARS = 4000

SILVER_SPLIT_FRACTIONS = {"train": 0.80, "dev": 0.20}

RANDOM_SEED = 20260730
