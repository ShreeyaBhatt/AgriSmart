"""Dataset + transforms.

Training transforms deliberately push clean PlantVillage lab images toward
field conditions (crop, colour shift, blur, perspective, occlusion) so the model
generalises to real photos — the core difficulty of the challenge.
"""

from __future__ import annotations

from pathlib import Path

import torch
from torch.utils.data import DataLoader, Subset
from torchvision import transforms
from torchvision.datasets import ImageFolder

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def train_transform(img_size: int) -> transforms.Compose:
    return transforms.Compose([
        transforms.RandomResizedCrop(img_size, scale=(0.6, 1.0), ratio=(0.75, 1.33)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomApply([transforms.ColorJitter(0.3, 0.3, 0.3, 0.08)], p=0.8),
        transforms.RandomApply([transforms.GaussianBlur(3, sigma=(0.1, 1.6))], p=0.3),
        transforms.RandomPerspective(distortion_scale=0.3, p=0.3),
        transforms.RandomGrayscale(p=0.03),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        transforms.RandomErasing(p=0.25, scale=(0.02, 0.15)),
    ])


def eval_transform(img_size: int) -> transforms.Compose:
    return transforms.Compose([
        transforms.Resize(int(img_size * 1.14)),
        transforms.CenterCrop(img_size),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def make_loaders(
    data_dir: str | Path, img_size: int, batch_size: int, val_frac: float = 0.15, seed: int = 42,
) -> tuple[DataLoader, DataLoader, list[str]]:
    base = ImageFolder(str(data_dir))  # no transform yet; applied per-split below
    classes = base.classes

    n = len(base)
    g = torch.Generator().manual_seed(seed)
    perm = torch.randperm(n, generator=g).tolist()
    n_val = max(1, int(n * val_frac))
    val_idx, train_idx = perm[:n_val], perm[n_val:]

    train_ds = ImageFolder(str(data_dir), transform=train_transform(img_size))
    val_ds = ImageFolder(str(data_dir), transform=eval_transform(img_size))

    train_loader = DataLoader(Subset(train_ds, train_idx), batch_size=batch_size,
                              shuffle=True, num_workers=0, drop_last=False)
    val_loader = DataLoader(Subset(val_ds, val_idx), batch_size=batch_size,
                            shuffle=False, num_workers=0)
    return train_loader, val_loader, classes
