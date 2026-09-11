#!/usr/bin/env python3
"""Run the predict interface over a labelled folder and write the model report.

    python model/evaluate.py --dir data/plantvillage --out report/model_report.md

``--dir`` is an ImageFolder (``<class>/<image>``). Reports macro-F1 (primary),
accuracy, per-class precision/recall and the confusion matrix, plus the
abstention rate.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from sklearn.metrics import classification_report, confusion_matrix, f1_score

try:
    from .predict import predict_detailed
    from .labels import ABSTAIN_LABEL
    from .infer import model_version
except ImportError:
    from predict import predict_detailed
    from labels import ABSTAIN_LABEL
    from infer import model_version

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".JPG", ".JPEG", ".PNG"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("report/model_report.md"))
    ap.add_argument("--limit-per-class", type=int, default=60)
    args = ap.parse_args()

    class_dirs = sorted(p for p in args.dir.iterdir() if p.is_dir())
    classes = [p.name for p in class_dirs]
    y_true, y_pred, abstained = [], [], 0

    for cdir in class_dirs:
        imgs = [p for p in sorted(cdir.iterdir()) if p.suffix in IMG_EXT][: args.limit_per_class]
        for img in imgs:
            out = predict_detailed(str(img))
            y_true.append(cdir.name)
            if out["abstained"]:
                abstained += 1
                y_pred.append("__abstain__")
            else:
                y_pred.append(out["raw_class"])
        print(f"  {cdir.name:52s} {len(imgs)} images")

    labels = classes + ["__abstain__"]
    macro_f1 = f1_score(y_true, y_pred, labels=classes, average="macro", zero_division=0)
    acc = sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true)
    report = classification_report(y_true, y_pred, labels=classes, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    lines = [
        "# Model report — AgriSmart crop-disease classifier", "",
        f"- **Model:** {model_version()} (timm EfficientNet-B0, transfer learning)",
        f"- **Eval set:** `{args.dir}` — {len(y_true)} images, {len(classes)} classes "
        f"(≤{args.limit_per_class}/class)",
        "- **Split note:** internal PlantVillage subset. The hackathon's held-out "
        "field test set is scored by the organisers via `model/predict.py`.", "",
        "## Metrics", "",
        f"| Metric | Value |", "|---|---|",
        f"| Macro-F1 (primary) | **{macro_f1:.3f}** |",
        f"| Accuracy | {acc:.3f} |",
        f"| Abstention rate | {abstained/len(y_true):.3f} ({abstained}/{len(y_true)}) |", "",
        "## Per-class precision / recall / F1", "", "```", report, "```", "",
        "## Confusion matrix", "",
        "Rows = true, columns = predicted (last row/col = abstain).", "", "```",
        " ".join(f"{c[:14]:>14}" for c in ["true\\pred"] + labels),
    ]
    for name, row in zip(labels, cm.tolist()):
        lines.append(f"{name[:14]:>14} " + " ".join(f"{v:>14}" for v in row))
    lines += ["```", "",
              "## Limitations",
              "- Trained on lab-condition PlantVillage images; real field photos "
              "(clutter, mixed lighting, multiple leaves) are harder — the training "
              "augmentation and test-time abstention address this but do not eliminate it.",
              "- Subset of ~18 classes; retrain on the official kickoff label list when available."]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    (args.out.parent / "eval_metrics.json").write_text(json.dumps({
        "macro_f1": macro_f1, "accuracy": acc,
        "abstention_rate": abstained / len(y_true), "n": len(y_true),
        "class_distribution": dict(Counter(y_true)),
    }, indent=2))
    print(f"\nmacro-F1={macro_f1:.3f}  accuracy={acc:.3f}  -> {args.out}")


if __name__ == "__main__":
    main()
