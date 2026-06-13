import os
from unittest.mock import patch

from opentrader.main import _chart_redirect_url, _port_open


def test_port_open_local():
    assert _port_open("127.0.0.1", 65530) is False


def test_chart_redirect_when_api_on_8011_and_chart_on_8010():
    with patch.dict(
        os.environ,
        {"PORT": "8011", "OPENTRADER_CHART_PORT": "8010", "OPENTRADER_API_ONLY": "1"},
        clear=False,
    ):
        assert _chart_redirect_url() == "http://127.0.0.1:8010/"


def test_no_redirect_when_same_port():
    with patch.dict(os.environ, {"PORT": "8010", "OPENTRADER_CHART_PORT": "8010"}, clear=False):
        assert _chart_redirect_url() is None
