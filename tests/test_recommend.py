"""Amendment engine — graceful degradation when SHC nutrients are missing."""

from datetime import datetime, timezone

import pytest

from app.backend.models.soil import SoilProfile
from app.backend.services.recommend import recommend_amendments, recommend_crops


def _profile(**overrides) -> SoilProfile:
    base = dict(
        source="SoilGrids v2.0",
        fetched_at=datetime.now(timezone.utc),
        lat=22.31, lon=73.18,
        texture_class="clay",
        wrb_class="Vertisols",
        sand_pct=27.9, silt_pct=26.8, clay_pct=45.3,
        ph=7.83, organic_carbon_pct=0.67, cec_cmol_kg=32.3,
        total_nitrogen_g_kg=0.77,
    )
    base.update(overrides)
    return SoilProfile(**base)


def test_amendments_from_soilgrids_only_flags_npk_gaps():
    report = recommend_amendments(_profile())
    cats = {a.category for a in report.amendments}
    assert "ph" in cats and "organic_matter" in cats and "cec" in cats and "texture" in cats
    # no SHC data -> P and K become explicit data gaps, not silent
    assert any("phosphorus" in g.lower() for g in report.data_gaps)
    assert any("potassium" in g.lower() for g in report.data_gaps)
    assert report.citation


def test_amendments_use_shc_values_when_present():
    report = recommend_amendments(
        _profile(available_n_kg_ha=245, available_p_kg_ha=8, available_k_kg_ha=305)
    )
    by_cat = {a.category: a for a in report.amendments}
    assert by_cat["phosphorus"].severity == "low"      # 8 < 10 kg/ha
    assert by_cat["potassium"].severity == "high"      # 305 > 280 kg/ha
    assert report.data_gaps == []


def test_amendments_acidic_soil_recommends_lime():
    report = recommend_amendments(_profile(ph=5.1))
    ph_rec = next(a for a in report.amendments if a.category == "ph")
    assert ph_rec.severity == "low"
    assert "lime" in ph_rec.action.lower()


def test_crop_ranking_prefers_texture_and_ph_match():
    rec = recommend_crops(_profile(texture_class="clay", ph=7.0), season="kharif")
    assert rec.ranked[0].score >= rec.ranked[-1].score
    top = {c.crop for c in rec.ranked[:3]}
    assert "Cotton" in top or "Rice" in top      # both love heavy clay in kharif
    assert "Module C" in rec.note
