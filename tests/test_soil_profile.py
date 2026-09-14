"""Normalisation, SHC enrichment, and the offline fallback of the soil pipeline."""

import asyncio
import json

import pytest

from app.backend.config import get_settings
from app.backend.models.soil import SoilProfile
from app.backend.services import soil_profile as sp
from app.backend.services.geocode import Admin
from app.backend.services.shc import ShcRecord
from app.backend.services.soilgrids_client import SoilGridsError, properties_have_values


@pytest.fixture
def sample_doc():
    return json.loads(get_settings().soilgrids_sample_path.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _clear_cache():
    sp.clear_cache()
    yield
    sp.clear_cache()


# --------------------------------------------------------------------------- #
# pure normalisation
# --------------------------------------------------------------------------- #
def test_normalise_properties_depth_weighted_and_unit_converted(sample_doc):
    values, uncertainty = sp.normalise_properties(sample_doc["properties"])

    assert values["clay"] == pytest.approx(45.33, abs=0.1)   # (440,450,460)/10, 5:10:15 weights
    assert values["phh2o"] == pytest.approx(7.83, abs=0.02)  # pH*10 -> pH
    assert values["soc"] == pytest.approx(6.73, abs=0.05)    # dg/kg -> g/kg
    assert values["nitrogen"] == pytest.approx(0.767, abs=0.01)  # cg/kg -> g/kg
    assert values["cec"] == pytest.approx(32.33, abs=0.1)    # mmol(c)/kg -> cmol(c)/kg
    assert values["bdod"] == pytest.approx(1.433, abs=0.01)  # cg/cm3 -> kg/dm3
    assert values["cfvo"] == pytest.approx(2.07, abs=0.1)    # cm3/dm3 -> %
    assert uncertainty["phh2o"] is not None


def test_properties_have_values(sample_doc):
    assert properties_have_values(sample_doc["properties"]) is True
    all_null = {"properties": {"layers": [
        {"name": "clay", "depths": [{"label": "0-5cm", "values": {"mean": None, "uncertainty": None}}]},
    ]}}
    assert properties_have_values(all_null) is False
    assert properties_have_values({}) is False


def test_parse_classification(sample_doc):
    name, prob = sp.parse_classification(sample_doc["classification"])
    assert name == "Vertisols"
    assert prob == pytest.approx(0.58)


def test_assemble_profile_derives_texture_and_merges_shc(sample_doc):
    profile = sp.assemble_profile(
        lat=22.31, lon=73.18,
        properties_payload=sample_doc["properties"],
        classification_payload=sample_doc["classification"],
        admin=Admin("Vadodara", "Gujarat", "India"),
        shc=ShcRecord(245, 21, 305, "Vadodara", "Gujarat", "SHC portal"),
        source_prefix="SoilGrids v2.0",
    )
    assert isinstance(profile, SoilProfile)
    assert profile.texture_class == "clay"
    assert profile.wrb_class == "Vertisols"
    assert profile.ph == pytest.approx(7.83, abs=0.02)
    assert profile.organic_carbon_pct == pytest.approx(0.673, abs=0.01)
    assert profile.available_p_kg_ha == 21
    assert profile.source == "SoilGrids v2.0 + SHC (Vadodara)"
    assert profile.raw["properties"] and profile.raw["classification"]


def test_assemble_profile_without_shc_keeps_plain_source(sample_doc):
    profile = sp.assemble_profile(
        lat=22.31, lon=73.18,
        properties_payload=sample_doc["properties"],
        classification_payload=sample_doc["classification"],
        admin=Admin(None, None, None),
        shc=None,
        source_prefix="SoilGrids v2.0",
    )
    assert profile.source == "SoilGrids v2.0"
    assert profile.available_n_kg_ha is None
    assert profile.available_p_kg_ha is None


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
async def test_build_soil_profile_happy_path(monkeypatch, sample_doc):
    async def fake_props(lat, lon):
        return sample_doc["properties"]

    async def fake_class(lat, lon, number_classes=3):
        return sample_doc["classification"]

    async def fake_admin(lat, lon):
        return Admin("Vadodara", "Gujarat", "India")

    monkeypatch.setattr(sp, "fetch_properties", fake_props)
    monkeypatch.setattr(sp, "fetch_classification", fake_class)
    monkeypatch.setattr(sp, "reverse_admin", fake_admin)

    profile = await sp.build_soil_profile(22.31, 73.18)

    assert profile.texture_class == "clay"
    assert profile.source == "SoilGrids v2.0 + SHC (Vadodara)"   # merged from data/shc_reference/gujarat.json
    assert profile.available_k_kg_ha == 305


async def test_build_soil_profile_texture_override(monkeypatch, sample_doc):
    async def fake_props(lat, lon):
        return sample_doc["properties"]

    async def fake_class(lat, lon, number_classes=3):
        return sample_doc["classification"]

    async def fake_admin(lat, lon):
        return Admin("Vadodara", "Gujarat", "India")

    monkeypatch.setattr(sp, "fetch_properties", fake_props)
    monkeypatch.setattr(sp, "fetch_classification", fake_class)
    monkeypatch.setattr(sp, "reverse_admin", fake_admin)

    profile = await sp.build_soil_profile(22.31, 73.18, texture_override="sandy loam")

    assert profile.texture_class == "sandy loam"
    assert profile.source == "SoilGrids v2.0 + SHC (Vadodara)"


async def test_build_soil_profile_offline_fallback(monkeypatch, sample_doc):
    async def boom(lat, lon):
        raise SoilGridsError("network down / all-null payload")

    async def fake_class(lat, lon, number_classes=3):
        return sample_doc["classification"]

    async def no_admin(lat, lon):
        return Admin(None, None, None)

    monkeypatch.setattr(sp, "fetch_properties", boom)
    monkeypatch.setattr(sp, "fetch_classification", fake_class)
    monkeypatch.setattr(sp, "reverse_admin", no_admin)

    profile = await sp.build_soil_profile(22.31, 73.18, use_cache=False)

    assert profile.source == "regional estimate (offline)"
    assert profile.texture_class == "sandy clay loam"    # from the Default fallback
    assert profile.wrb_class == "Vertisols"         # real classification still used
    assert profile.available_p_kg_ha is None        # no district resolved


async def test_offline_fallback_keeps_shc_enrichment(monkeypatch, sample_doc):
    """Properties null, but reverse-geocode + SHC resolve -> nutrients still populate."""
    async def boom(lat, lon):
        raise SoilGridsError("all-null payload")

    async def fake_class(lat, lon, number_classes=3):
        return {}

    async def vadodara(lat, lon):
        return Admin("Vadodara", "Gujarat", "India")

    monkeypatch.setattr(sp, "fetch_properties", boom)
    monkeypatch.setattr(sp, "fetch_classification", fake_class)
    monkeypatch.setattr(sp, "reverse_admin", vadodara)

    profile = await sp.build_soil_profile(22.31, 73.18, use_cache=False)

    assert profile.source == "regional estimate (offline)"     # honest about the physical data
    assert profile.available_p_kg_ha == 21          # real SHC nutrients still merged
    assert profile.shc_district == "Vadodara"


async def test_build_soil_profile_uses_cache(monkeypatch, sample_doc):
    calls = {"n": 0}

    async def counting_props(lat, lon):
        calls["n"] += 1
        return sample_doc["properties"]

    async def fake_class(lat, lon, number_classes=3):
        return sample_doc["classification"]

    async def fake_admin(lat, lon):
        return Admin(None, None, None)

    monkeypatch.setattr(sp, "fetch_properties", counting_props)
    monkeypatch.setattr(sp, "fetch_classification", fake_class)
    monkeypatch.setattr(sp, "reverse_admin", fake_admin)

    await sp.build_soil_profile(19.0, 73.0)
    await sp.build_soil_profile(19.0, 73.0)
    assert calls["n"] == 1


async def test_build_soil_profile_caches_offline_fallback(monkeypatch, sample_doc):
    """Regression test: the offline-sample result wasn't cached at all before
    — every request for a location SoilGrids was failing on independently
    paid the full retry cost, even the exact same coordinates twice in a
    row. A second call for the same spot must not re-hit fetch_properties."""
    calls = {"n": 0}

    async def counting_boom(lat, lon):
        calls["n"] += 1
        raise SoilGridsError("network down / all-null payload")

    async def fake_class(lat, lon, number_classes=3):
        return sample_doc["classification"]

    async def fake_admin(lat, lon):
        return Admin(None, None, None)

    monkeypatch.setattr(sp, "fetch_properties", counting_boom)
    monkeypatch.setattr(sp, "fetch_classification", fake_class)
    monkeypatch.setattr(sp, "reverse_admin", fake_admin)

    p1 = await sp.build_soil_profile(21.0, 74.0)
    p2 = await sp.build_soil_profile(21.0, 74.0)
    assert calls["n"] == 1
    assert p1.source == p2.source == "regional estimate (offline)"


async def test_build_soil_profile_respects_deadline(monkeypatch, sample_doc):
    """A single lookup must never hang past soilgrids_deadline_s, no matter
    how long the underlying calls take (profiled a real ISRIC slowdown at
    50-60s+ for one lookup before this existed)."""
    monkeypatch.setattr(get_settings(), "soilgrids_deadline_s", 0.05)

    async def hangs_forever(lat, lon):
        await asyncio.sleep(10)
        return sample_doc["properties"]

    async def fake_class(lat, lon, number_classes=3):
        return sample_doc["classification"]

    async def fake_admin(lat, lon):
        return Admin(None, None, None)

    monkeypatch.setattr(sp, "fetch_properties", hangs_forever)
    monkeypatch.setattr(sp, "fetch_classification", fake_class)
    monkeypatch.setattr(sp, "reverse_admin", fake_admin)

    profile = await sp.build_soil_profile(21.0, 74.0, use_cache=False)
    assert profile.source == "regional estimate (offline)"
