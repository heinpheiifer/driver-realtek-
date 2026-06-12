from fastapi.testclient import TestClient

from opentrader.main import app

client = TestClient(app)


def test_opentrader_history_endpoint():
    response = client.get(
        "/api/history/",
        params={
            "symbol": "XRPUSD",
            "interval": "1m",
            "range": "1d",
            "source": "synthetic",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "XRPUSD"
    assert data["interval"] == "1m"
    assert data["count"] > 0
    assert len(data["bars"]) == data["count"]
    bar = data["bars"][0]
    assert {"time", "open", "high", "low", "close", "volume"}.issubset(bar)


def test_opentrader_mt5_status_slash():
    response = client.get("/api/mt5/status/")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data
    assert "mt5" in data


def test_bookmap_status_no_redirect():
    response = client.get("/api/bookmap/status/", follow_redirects=False)
    assert response.status_code == 200
