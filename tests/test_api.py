from fastapi.testclient import TestClient

from opentrader.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "OpenTrader"
    assert "modules" in data


def test_market_sources():
    response = client.get("/api/market/sources")
    assert response.status_code == 200
    data = response.json()
    source_ids = {item["id"] for item in data["sources"]}
    assert {"yahoo", "blackbull", "csv"}.issubset(source_ids)
    assert data["default_symbol"] == "BTCUSD"


def test_symbols():
    response = client.get("/api/symbols")
    assert response.status_code == 200
    data = response.json()
    assert "symbols" in data
    assert "count" in data
    assert isinstance(data["symbols"], list)
    assert data["count"] > 0


def test_symbols_trailing_slash_search():
    response = client.get(
        "/api/symbols/",
        params={"source": "blackbull", "q": "btc", "limit": 300},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0
    assert any("BTC" in sym.upper() for sym in data["symbols"])


def test_candles_synthetic_source():
    response = client.get(
        "/api/candles",
        params={
            "symbol": "BTCUSD",
            "source": "synthetic",
            "timeframe": "M5",
            "bars": 40,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSD"
    assert data["is_synthetic"] is True
    assert data["source"].startswith("synthetic:")
    assert data["count"] == 40
    assert len(data["candles"]) == 40
    assert "orderflow" in data
    candle = data["candles"][0]
    assert {"timestamp", "open", "high", "low", "close", "volume"}.issubset(candle)
