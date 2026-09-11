#!/usr/bin/env python3
"""Fine-tune the crop-disease classifier and write artifacts.

    python model/train.py --data-dir data/plantvillage --epochs 4 --out model/artifacts

Transfer learning: epoch 1 trains the head only, then the whole network is
unfrozen. Temperature scaling is fitted on the validation split. Outputs
``weights.pt``, ``class_map.json``, ``temperature.pt``, ``metrics.json``.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix, f1_score

from dataset import make_loaders  # noqa: E402
from net import DEFAULT_BACKBONE, build_model  # noqa: E402


def _set_backbone_trainable(model: nn.Module, trainable: bool) -> None:
    head = model.get_classifier()
    for p in model.parameters():
        p.requires_grad = trainable
    for p in head.parameters():
        p.requires_grad = True


@torch.no_grad()
def _collect_logits(model: nn.Module, loader, device: str) -> tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    logits, targets = [], []
    for x, y in loader:
        logits.append(model(x.to(device)).cpu())
        targets.append(y)
    return torch.cat(logits), torch.cat(targets)


def _fit_temperature(logits: torch.Tensor, targets: torch.Tensor) -> float:
    """Optimise a single scalar T minimising NLL on held-out logits."""
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=60)
    nll = nn.CrossEntropyLoss()

    def closure():
        opt.zero_grad()
        loss = nll(logits / log_t.exp(), targets)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp().item())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("data/plantvillage"))
    ap.add_argument("--out", type=Path, default=Path("model/artifacts"))
    ap.add_argument("--backbone", default=DEFAULT_BACKBONE)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--img-size", type=int, default=192)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if not args.data_dir.is_dir():
        raise SystemExit(f"{args.data_dir} not found — run model/download_data.py first "
                         "or pass --data-dir to an ImageFolder.")

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    args.out.mkdir(parents=True, exist_ok=True)

    train_loader, val_loader, classes = make_loaders(
        args.data_dir, args.img_size, args.batch_size, seed=args.seed
    )
    print(f"device={device}  classes={len(classes)}  "
          f"train={len(train_loader.dataset)}  val={len(val_loader.dataset)}")

    model = build_model(len(classes), backbone=args.backbone, pretrained=True).to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)

    for epoch in range(1, args.epochs + 1):
        _set_backbone_trainable(model, trainable=epoch > 1)
        params = [p for p in model.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=args.lr if epoch > 1 else args.lr * 3, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=len(train_loader))

        model.train()
        t0, running, seen, correct = time.time(), 0.0, 0, 0
        for i, (x, y) in enumerate(train_loader, 1):
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            out = model(x)
            loss = criterion(out, y)
            loss.backward()
            opt.step()
            sched.step()
            running += loss.item() * x.size(0)
            seen += x.size(0)
            correct += (out.argmax(1) == y).sum().item()
            if i % 20 == 0:
                print(f"  epoch {epoch} [{i}/{len(train_loader)}] "
                      f"loss={running/seen:.3f} acc={correct/seen:.3f}")
        print(f"epoch {epoch} done in {time.time()-t0:.0f}s  "
              f"train_loss={running/seen:.3f} train_acc={correct/seen:.3f}")

    # ---- validation + temperature ----
    val_logits, val_targets = _collect_logits(model, val_loader, device)
    temperature = _fit_temperature(val_logits, val_targets)
    preds = (val_logits / temperature).argmax(1).numpy()
    y_true = val_targets.numpy()

    macro_f1 = float(f1_score(y_true, preds, average="macro"))
    acc = float((preds == y_true).mean())
    report = classification_report(y_true, preds, target_names=classes, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, preds).tolist()
    print(f"\nval  macro-F1={macro_f1:.3f}  accuracy={acc:.3f}  temperature={temperature:.3f}")

    torch.save(model.state_dict(), args.out / "weights.pt")
    (args.out / "class_map.json").write_text(
        json.dumps({"classes": classes, "backbone": args.backbone, "img_size": args.img_size}, indent=2)
    )
    torch.save({"temperature": temperature}, args.out / "temperature.pt")
    (args.out / "metrics.json").write_text(json.dumps({
        "split": "internal val (15% of downloaded PlantVillage subset)",
        "classes": classes, "n_val": int(len(y_true)),
        "macro_f1": macro_f1, "accuracy": acc,
        "per_class": report, "confusion_matrix": cm,
    }, indent=2))
    print(f"saved artifacts -> {args.out}")


if __name__ == "__main__":
    main()
