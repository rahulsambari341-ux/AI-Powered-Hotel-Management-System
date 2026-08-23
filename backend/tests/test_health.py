def test_root(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_health_db(client):
    res = client.get("/health/db")
    assert res.status_code == 200
    assert res.json()["database"] == "connected"
