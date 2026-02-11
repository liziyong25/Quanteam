from fastapi.testclient import TestClient

from quant_eam.api.app import app


def test_healthz() -> None:
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_version() -> None:
    client = TestClient(app)
    r = client.get("/version")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "0.0.0"
    # git_sha is optional
    if "git_sha" in data:
        assert isinstance(data["git_sha"], str)
