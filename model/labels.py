"""Shared class list + label helpers.

Labels are the PlantVillage folder names (used verbatim as the `predict` output
string). When the hackathon's kickoff dataset ships its own label list, retrain
with those folder names — nothing else changes.
"""

from __future__ import annotations

# The subset we train on: PS-relevant crop/disease pairs that exist in PlantVillage,
# plus the matching "healthy" classes.
DEFAULT_CLASSES: tuple[str, ...] = (
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___healthy",
    "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___healthy",
    "Grape___Black_rot",
    "Grape___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___healthy",
)

ABSTAIN_LABEL = "unclear image — please retake the photo"


def pretty(label: str) -> str:
    """'Tomato___Late_blight' -> 'Tomato — Late blight'."""
    crop, _, rest = label.partition("___")
    return f"{crop.replace('_', ' ')} — {rest.replace('_', ' ').strip()}"


def is_healthy(label: str) -> bool:
    return label.endswith("healthy")
