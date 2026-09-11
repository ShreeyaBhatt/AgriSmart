"""Model construction + loading trained artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import timm
import torch
import torch.nn as nn

DEFAULT_BACKBONE = "efficientnet_b0"


def build_model(num_classes: int, backbone: str = DEFAULT_BACKBONE, pretrained: bool = True) -> nn.Module:
    return timm.create_model(backbone, pretrained=pretrained, num_classes=num_classes)


class TrainedModel:
    """A loaded classifier + its class map + fitted temperature."""

    def __init__(self, model: nn.Module, classes: list[str], temperature: float, backbone: str):
        self.model = model.eval()
        self.classes = classes
        self.temperature = max(float(temperature), 1e-3)
        self.backbone = backbone

    @torch.no_grad()
    def probabilities(self, batch: torch.Tensor) -> torch.Tensor:
        """batch: (N, 3, H, W) normalised -> (N, C) temperature-scaled softmax."""
        logits = self.model(batch) / self.temperature
        return torch.softmax(logits, dim=1)


def load_trained(artifacts_dir: str | Path) -> TrainedModel:
    d = Path(artifacts_dir)
    class_map = json.loads((d / "class_map.json").read_text(encoding="utf-8"))
    classes: list[str] = class_map["classes"]
    backbone: str = class_map.get("backbone", DEFAULT_BACKBONE)

    model = build_model(len(classes), backbone=backbone, pretrained=False)
    state = torch.load(d / "weights.pt", map_location="cpu")
    model.load_state_dict(state)

    temperature = 1.0
    tpath = d / "temperature.pt"
    if tpath.exists():
        temperature = float(torch.load(tpath, map_location="cpu")["temperature"])

    return TrainedModel(model, classes, temperature, backbone)
