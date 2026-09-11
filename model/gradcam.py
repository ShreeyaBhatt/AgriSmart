"""Grad-CAM overlay — shows the farmer which part of the leaf drove the call."""

from __future__ import annotations

import logging

import numpy as np
import torch
from PIL import Image

log = logging.getLogger(__name__)


def _target_layers(model: torch.nn.Module) -> list:
    # timm EfficientNet: last conv block; fall back to conv_head or the last child.
    for attr in ("blocks", "conv_head"):
        mod = getattr(model, attr, None)
        if mod is not None:
            return [mod[-1] if attr == "blocks" else mod]
    return [list(model.children())[-2]]


def overlay(model: torch.nn.Module, input_tensor: torch.Tensor, base_image: Image.Image,
            class_idx: int, img_size: int = 192) -> Image.Image | None:
    """Return an RGB heat-map overlay, or None if Grad-CAM is unavailable."""
    try:
        from pytorch_grad_cam import GradCAM
        from pytorch_grad_cam.utils.image import show_cam_on_image
        from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

        cam = GradCAM(model=model, target_layers=_target_layers(model))
        grayscale = cam(input_tensor=input_tensor, targets=[ClassifierOutputTarget(class_idx)])[0]

        rgb = np.asarray(base_image.convert("RGB").resize((img_size, img_size)), dtype=np.float32) / 255.0
        vis = show_cam_on_image(rgb, grayscale, use_rgb=True)
        return Image.fromarray(vis)
    except Exception as exc:
        log.warning("Grad-CAM failed: %s", exc)
        return None
