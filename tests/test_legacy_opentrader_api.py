from fastapi.testclient import TestClient

from opentrader.main import app

client = TestClient(app)


def test_opentrader_history_blackbull_fallback():
    """When blackbull empty, history should still return 200 via yahoo/synthetic."""
    response = client.get(
        "/api/history/",
        params={
            "symbol": "XRPUSD",
            "interval": "1m",
            "range": "1d",
            "source": "blackbull",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["source"] == "blackbull"
    assert data["count"] > 0
    assert len(data["bars"]) > 0
    bar = data["bars"][0]
    assert bar["time"] > 0
    assert "t" in bar and bar["t"] == bar["time"]


def test_opentrader_mt5_status_slash():
    response = client.get("/api/mt5/status/")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data
    assert "mt5" in data


def test_bookmap_status_no_redirect():
    response = client.get("/api/bookmap/status/", follow_redirects=False)
    assert response.status_code == 200
