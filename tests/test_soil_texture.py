"""USDA texture triangle — corner cases and the classes named in the plan."""

import pytest

from app.backend.services.soil_texture import USDA_CLASSES, usda_texture


@pytest.mark.parametrize(
    ("sand", "silt", "clay", "expected"),
    [
        # plan verification cases
        (20, 20, 60, "clay"),
        (40, 40, 20, "loam"),
        (70, 20, 10, "sandy loam"),
        # triangle corners / centres
        (95, 3, 2, "sand"),
        (82, 12, 6, "loamy sand"),
        (65, 25, 10, "sandy loam"),
        (20, 65, 15, "silt loam"),
        (5, 88, 7, "silt"),
        (55, 15, 30, "sandy clay loam"),
        (32, 34, 34, "clay loam"),
        (10, 57, 33, "silty clay loam"),
        (52, 6, 42, "sandy clay"),
        (6, 48, 46, "silty clay"),
        (25, 25, 50, "clay"),
    ],
)
def test_usda_texture(sand, silt, clay, expected):
    assert usda_texture(sand, silt, clay) == expected


def test_result_is_always_a_known_class():
    for s in range(0, 101, 5):
        for si in range(0, 101 - s, 5):
            c = 100 - s - si
            assert usda_texture(s, si, c) in USDA_CLASSES


def test_unnormalised_input_is_renormalised():
    # same ratios as (28, 27, 45) but on a g/kg scale
    assert usda_texture(280, 270, 450) == usda_texture(28, 27, 45)


def test_zero_input_rejected():
    with pytest.raises(ValueError):
        usda_texture(0, 0, 0)
