from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from opentrader.main import app


def test_history_falls_back_when_django_proxy_returns_503():
    """Django 503 must not block local yahoo/synthetic fallback on /api/history/."""
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 503
    mock_resp.content = b'{"detail":"no blackbull data"}'
    mock_resp.headers = {"content-type": "application/json"}

    with patch.dict("os.environ", {"OPENTRADER_BACKEND_URL": "http://127.0.0.1:8000"}):
        with patch("opentrader.django_proxy.requests.request", return_value=mock_resp):
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
    assert len(data["bars"]) > 0
