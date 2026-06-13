from pathlib import Path


def test_django_frontend_serve_module_exists():
    path = Path(__file__).resolve().parents[1] / "opentrader/chart_patches/django_frontend_serve.py"
    text = path.read_text(encoding="utf-8")
    assert "def serve_index" in text
    assert "def serve_asset" in text
    assert (Path(__file__).resolve().parents[1] / "scripts/patch_django_frontend.sh").is_file()
