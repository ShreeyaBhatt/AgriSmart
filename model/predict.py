#!/usr/bin/env python3
"""The judged inference interface.

    from model.predict import predict
    predict("leaf.jpg")            # -> "Tomato___Late_blight"  (or the abstain string)

    python model/predict.py --image leaf.jpg

Pipeline: load image -> resize/normalise -> TTA (4 views, mean softmax) ->
temperature-scaled -> abstain if the top probability is below tau. Loads the
trained artifacts from ``model/artifacts`` (override with
``AGRISMART_MODEL_ARTIFACTS_DIR``). No manual steps.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import torch
from PIL import Image, ImageOps

try:  # imported as a package (from the FastAPI backend)
    from .net import load_trained
    from .labels import ABSTAIN_LABEL
    from .dataset import eval_transform
    from .foliage import verify_plant_foliage, evaluate_crop_support
except ImportError:  # run as a script
    from net import load_trained
    from labels import ABSTAIN_LABEL
    from dataset import eval_transform
    from foliage import verify_plant_foliage, evaluate_crop_support

ARTIFACTS_DIR = Path(os.getenv("AGRISMART_MODEL_ARTIFACTS_DIR",
                               str(Path(__file__).resolve().parent / "artifacts")))
# Single global cutoff for every class alike. Confident-wrong predictions
# have been reported in the field (see team notes) — worth investigating
# per-class thresholds and validating temperature scaling against a held-out
# calibration set rather than tuning this one number further.
TAU = float(os.getenv("AGRISMART_ABSTAIN_TAU", "0.40"))

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        if not (ARTIFACTS_DIR / "weights.pt").exists():
            raise FileNotFoundError(
                f"No trained model at {ARTIFACTS_DIR}. Run:\n"
                "  python model/download_data.py --out data/plantvillage\n"
                "  python model/train.py --data-dir data/plantvillage"
            )
        _MODEL = load_trained(ARTIFACTS_DIR)
    return _MODEL


def _tta_views(img: Image.Image, img_size: int) -> list[torch.Tensor]:
    tf = eval_transform(img_size)
    w, h = img.size
    zoom = img.crop((int(0.06 * w), int(0.06 * h), int(0.94 * w), int(0.94 * h)))
    return [tf(img), tf(ImageOps.mirror(img)), tf(zoom), tf(ImageOps.mirror(zoom))]


def predict_detailed(image_path: str) -> dict:
    """Full result: label, confidence, abstained flag, top-3, and rejection reason."""
    img = Image.open(image_path).convert("RGB")

    # 1. Botanical Foliage / Leaf Integrity Verification
    is_leaf, leaf_reason, foliage_metrics = verify_plant_foliage(img)
    if not is_leaf:
        return {
            "predicted_class": ABSTAIN_LABEL,
            "raw_class": ABSTAIN_LABEL,
            "confidence": 0.0,
            "abstained": True,
            "is_leaf": False,
            "rejection_reason": "not_a_leaf",
            "foliage_metrics": foliage_metrics,
            "top3": [],
        }

    tm = _model()
    img_size = 192
    try:
        from json import loads
        img_size = loads((ARTIFACTS_DIR / "class_map.json").read_text()).get("img_size", 192)
    except Exception:
        pass

    batch = torch.stack(_tta_views(img, img_size))
    probs = tm.probabilities(batch).mean(0)
    conf, idx = torch.max(probs, dim=0)
    conf = float(conf)
    top = torch.topk(probs, k=min(3, len(tm.classes)))
    top3 = [(tm.classes[i], float(p)) for p, i in zip(top.values, top.indices)]

    # 2. Supported Crop & Out-of-Distribution (OOD) Verification
    is_supported, crop_reason = evaluate_crop_support(conf, top3, min_confidence=max(TAU, 0.60))
    abstained = (not is_supported) or (conf < TAU)
    rejection_reason = "unsupported_crop" if (not is_supported) else None

    return {
        "predicted_class": ABSTAIN_LABEL if abstained else tm.classes[int(idx)],
        "raw_class": tm.classes[int(idx)],
        "confidence": round(conf, 4),
        "abstained": abstained,
        "is_leaf": True,
        "rejection_reason": rejection_reason,
        "foliage_metrics": foliage_metrics,
        "top3": top3,
    }


def predict(image_path: str) -> str:
    """Return the predicted class label string (or the abstain string)."""
    return predict_detailed(image_path)["predicted_class"]


def _cli() -> None:
    ap = argparse.ArgumentParser(description="Predict the crop disease for one leaf image.")
    ap.add_argument("--image", required=True, help="path to a leaf/crop image")
    args = ap.parse_args()
    print(predict(args.image))


if __name__ == "__main__":
    _cli()
