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


async def test_wcs_fetch_properties_structure(monkeypatch):
    """Test that fetch_properties returns the standard GeoJSON Feature schema expected downstream."""
    from app.backend.services import soilgrids_client as sgc

    async def fake_pixel(client, map_name, coverage_id, lat, lon, delta=0.03):
        # Return realistic raw sensor values
        mock_values = {
            "clay": 440, "sand": 290, "silt": 270, "phh2o": 77,
            "soc": 78, "nitrogen": 90, "cec": 310, "bdod": 138, "cfvo": 18,
        }
        return mock_values.get(map_name, 100)

    monkeypatch.setattr(sgc, "_fetch_wcs_pixel", fake_pixel)
    payload = await sgc.fetch_properties(22.31, 73.18)

    assert payload["type"] == "Feature"
    assert payload["geometry"]["coordinates"] == [73.18, 22.31]
    layers = payload["properties"]["layers"]
    assert len(layers) == len(sgc.PROPERTIES)
    clay_layer = next(l for l in layers if l["name"] == "clay")
    assert clay_layer["unit_measure"]["d_factor"] == 10
    assert len(clay_layer["depths"]) == 3
    assert clay_layer["depths"][0]["values"]["mean"] == 440


async def test_wcs_fetch_classification_mock(monkeypatch):
    """Test WRB integer raster decoding and class mapping."""
    import io
    from PIL import Image
    import numpy as np
    from app.backend.services import soilgrids_client as sgc

    # Create an in-memory TIFF image with pixel values = 29 (Vertisols)
    img = Image.fromarray(np.full((10, 10), 29, dtype=np.int16))
    buf = io.BytesIO()
    img.save(buf, format="TIFF")
    tiff_bytes = buf.getvalue()

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "image/tiff"}
        content = tiff_bytes

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, url, params=None):
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: FakeClient())
    result = await sgc.fetch_classification(22.31, 73.18)
    assert result["wrb_class_name"] == "Vertisols"
    assert result["wrb_class_probability"][0][0] == "Vertisols"
    assert result["wrb_class_probability"][0][1] == 100
