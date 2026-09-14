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
