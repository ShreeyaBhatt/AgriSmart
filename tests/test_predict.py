"""The /predict endpoint and the model's predict() interface."""

import io
from pathlib import Path

import pytest

_ARTIFACTS = Path(__file__).resolve().parents[1] / "model" / "artifacts"
_HAS_MODEL = (_ARTIFACTS / "weights.pt").exists()


@pytest.mark.asyncio
async def test_predict_requires_auth(client):
    r = await client.post("/api/predict", files={"file": ("x.png", b"x", "image/png")})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_predict_rejects_non_image(auth_client):
    client, headers, _ = auth_client
    r = await client.post("/api/predict", headers=headers,
                          files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415


@pytest.mark.asyncio
async def test_predict_is_graceful_without_a_trained_model(auth_client, monkeypatch):
    """Simulates missing weights via a monkeypatch rather than relying on
    model/artifacts/weights.pt actually being absent — that made this test
    (and its real-model counterpart below) mutually exclusive based on
    whatever happened to be checked out, so exactly one of the two always
    skipped. Patching run_inference itself means both run every time,
    regardless of repo state."""
    import model.infer as infer_module

    def _raise(*_a, **_k):
        raise FileNotFoundError("weights.pt not found")

    monkeypatch.setattr(infer_module, "run_inference", _raise)

    client, headers, _ = auth_client
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    r = await client.post("/api/predict", headers=headers,
                          files={"file": ("leaf.png", io.BytesIO(png), "image/png")})
    assert r.status_code == 503
    assert "not trained" in r.json()["detail"]


@pytest.mark.skipif(not _HAS_MODEL, reason="requires a trained model (run model/train.py)")
def test_predict_interface_returns_a_known_label():
    from model.net import load_trained
    from model.predict import predict

    classes = set(load_trained(_ARTIFACTS).classes) | {"unclear image — please retake the photo"}
    sample = next((_ARTIFACTS.parents[1] / "data" / "samples" / "leaves").glob("*.jpg"), None)
    assert sample is not None, "no sample leaf image bundled"
    label = predict(str(sample))
    assert label in classes


# --- Crop-aware guard rail (issue: OOD crops like Cotton get forced into
# one of the 6 trained classes with confident-looking, wrong-crop
# treatment steps) — needs the real model to produce a real crop label, so
# it's gated on _HAS_MODEL like the real-inference test above (not the
# monkeypatched "missing model" test, which doesn't touch real weights). --
_SAMPLE_LEAVES = _ARTIFACTS.parents[1] / "data" / "samples" / "leaves"


def _leaf_bytes(name: str) -> bytes:
    path = _SAMPLE_LEAVES / name
    assert path.exists(), f"sample leaf not bundled: {name}"
    return path.read_bytes()


@pytest.mark.skipif(not _HAS_MODEL, reason="requires a trained model (run model/train.py)")
@pytest.mark.asyncio
async def test_predict_flags_crop_mismatch_against_plot_main_crop(auth_client):
    client, headers, _ = auth_client
    plot = (await client.post("/api/plots", headers=headers, json={
        "name": "Cotton field", "lat": 22.3, "lon": 73.2, "main_crop": "Cotton",
    })).json()

    r = await client.post(
        "/api/predict", headers=headers,
        data={"plot_id": plot["id"]},
        files={"file": ("leaf.jpg", _leaf_bytes("Apple___Apple_scab.jpg"), "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["crop_warning"] is not None
    assert "Cotton" in body["crop_warning"]
    # Specific chemical/organic dosing must be suppressed on mismatch —
    # only the generic fallback precautions should show.
    assert body["precautions"] == [
        "Scout the crop again in 2-3 days",
        "Remove and destroy badly affected leaves",
        "Keep foliage dry — water at the base, early in the day",
    ]


@pytest.mark.skipif(not _HAS_MODEL, reason="requires a trained model (run model/train.py)")
@pytest.mark.asyncio
async def test_predict_no_warning_when_plot_crop_matches_prediction(auth_client):
    client, headers, _ = auth_client
    plot = (await client.post("/api/plots", headers=headers, json={
        "name": "Apple orchard", "lat": 22.3, "lon": 73.2, "main_crop": "Apple",
    })).json()

    r = await client.post(
        "/api/predict", headers=headers,
        data={"plot_id": plot["id"]},
        files={"file": ("leaf.jpg", _leaf_bytes("Apple___Apple_scab.jpg"), "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["crop_warning"] is None


@pytest.mark.skipif(not _HAS_MODEL, reason="requires a trained model (run model/train.py)")
@pytest.mark.asyncio
async def test_predict_falls_back_to_profile_crop_when_no_plot(auth_client):
    """auth_client's onboarding profile sets primary_crop="Cotton" (see
    conftest.py) — with no plot_id at all, that account-level crop should
    still be used for the mismatch check."""
    client, headers, user = auth_client
    assert user["primary_crop"] == "Cotton"

    r = await client.post(
        "/api/predict", headers=headers,
        files={"file": ("leaf.jpg", _leaf_bytes("Apple___Apple_scab.jpg"), "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["crop_warning"] is not None
