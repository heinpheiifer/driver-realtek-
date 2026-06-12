from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from opentrader.main import app


def test_history_always_200_without_django_proxy():
    client = TestClient(app)
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
    assert data["count"] > 0


def test_django_proxy_disabled_by_default():
    client = TestClient(app)
    health = client.get("/api/health").json()
    assert health.get("django_proxy") is False


def test_django_proxy_falls_through_on_backend_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.content = b'{"detail":"no data"}'
    mock_resp.headers = {"content-type": "application/json"}

    with patch.dict(
        "os.environ",
        {
            "OPENTRADER_DJANGO_PROXY": "1",
            "OPENTRADER_BACKEND_URL": "http://127.0.0.1:8000",
        },
    ):
        with patch("opentrader.django_proxy.requests.request", return_value=mock_resp):
            client = TestClient(app)
            response = client.get(
                "/api/candles",
                params={"symbol": "XRPUSD", "timeframe": "M1", "source": "blackbull"},
            )
    assert response.status_code == 200
