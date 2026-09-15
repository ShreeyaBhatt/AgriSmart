"""Botanical foliage verification & Out-Of-Distribution (OOD) crop guard.

Detects:
1. Non-leaf / non-plant inputs (e.g. human face, furniture, shoes, vehicles,
   electronic screens, solid colors, text documents, arbitrary objects).
2. Leaves of unsupported crops or ambiguous out-of-distribution foliage.

Suppresses false disease predictions and prevents hazardous, hallucinated
chemical or organic treatment recommendations on non-crop images.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)


def verify_plant_foliage(img: Image.Image) -> tuple[bool, str, dict[str, Any]]:
    """Evaluates whether an input image depicts genuine plant foliage / leaf tissue.

    Returns:
        (is_foliage, rejection_reason, diagnostic_metrics)
    """
    rgb = np.array(img.convert("RGB"), dtype=np.float32)
    hsv = np.array(img.convert("HSV"), dtype=np.float32)

    h = hsv[:, :, 0]          # 0..255 (maps to 0..360 deg)
    s = hsv[:, :, 1] / 255.0  # 0..1
    v = hsv[:, :, 2] / 255.0  # 0..1

    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]

    # 1. Botanical Pigmentation Spectrum
    # A) Chlorophyll greens: Hue in ~40° to ~165° (28 to 118 in 0..255 scale)
    green_mask = (h >= 28) & (h <= 118) & (s >= 0.10) & (v >= 0.08)

    # B) Chlorotic / yellow-green / lesion halos: Hue in ~18° to ~40° (13 to 28)
    yellow_mask = (h >= 13) & (h < 28) & (s >= 0.12) & (v >= 0.10) & (g >= b * 0.90)

    # C) Necrotic / dried brown leaf tissue / fungal spots: Hue in ~8° to ~25° (6 to 18)
    necrotic_mask = (
        (h >= 6) & (h < 18) & (s >= 0.12) & (v >= 0.06) & (v <= 0.88)
        & (r >= g) & (g >= b * 0.75)
    )

    foliar_mask = green_mask | yellow_mask | necrotic_mask
    foliar_ratio = float(np.mean(foliar_mask))

    # 2. Texture & Natural Lighting Variance
    std_rgb = np.std(rgb, axis=(0, 1))
    mean_std = float(np.mean(std_rgb))

    # 3. Chromatic Spread (Rejects monochrome / grayscale)
    color_spread = float(np.mean(np.abs(r - g) + np.abs(g - b) + np.abs(r - b)))

    metrics = {
        "foliar_ratio": round(foliar_ratio, 4),
        "mean_std": round(mean_std, 2),
        "color_spread": round(color_spread, 2),
    }

    # Flat synthetic graphics / solid colors (screens, artificial graphics)
    if mean_std < 8.0:
        return False, "flat_synthetic_color", metrics

    # Grayscale, documents, black & white screens
    if color_spread < 6.0:
        return False, "grayscale_monochrome", metrics

    # Lack of plant foliar pigment (shoes, cars, sky, furniture, red/blue objects, skin)
    if foliar_ratio < 0.10:
        return False, "non_plant_spectrum", metrics

    return True, "valid_foliage", metrics


def evaluate_crop_support(
    confidence: float,
    top3: list[tuple[str, float]],
    min_confidence: float = 0.65,
    min_margin: float = 0.15,
) -> tuple[bool, str]:
    """Determines if a prediction represents a high-confidence in-distribution crop
    from the 18 trained classes, rather than an unsupported plant or ambiguous leaf.
    """
    if confidence < min_confidence:
        return False, "low_confidence"

    if len(top3) >= 2:
        top1_prob = top3[0][1]
        top2_prob = top3[1][1]
        margin = top1_prob - top2_prob
        if margin < min_margin:
            return False, "diffuse_probability"

    return True, "supported_crop"
