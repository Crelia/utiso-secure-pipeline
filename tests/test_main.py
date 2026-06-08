from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_version_shape():
    resp = client.get("/version")
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body and "git_sha" in body


def test_hash_is_correct():
    resp = client.post("/api/hash", json={"text": "hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["algorithm"] == "sha256"
    # sha256("hello")
    assert body["hex"] == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_hash_rejects_empty():
    resp = client.post("/api/hash", json={"text": ""})
    assert resp.status_code == 422


def test_security_headers_present():
    resp = client.get("/healthz")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in resp.headers["content-security-policy"]
