import subprocess
from pathlib import Path


def test_patch_django_firefox_allowed_hosts(tmp_path):
    root = Path(__file__).resolve().parents[1]
    chart = tmp_path / "OpenTrader"
    proj = chart / "opentrader_project"
    proj.mkdir(parents=True)
    (chart / "manage.py").write_text("# django\n", encoding="utf-8")
    settings = proj / "settings.py"
    settings.write_text(
        "ALLOWED_HOSTS = []\nINSTALLED_APPS = []\nMIDDLEWARE = []\n",
        encoding="utf-8",
    )

    subprocess.run(
        ["bash", str(root / "scripts/patch_django_firefox.sh"), str(chart)],
        check=True,
        capture_output=True,
        text=True,
    )

    text = settings.read_text(encoding="utf-8")
    assert "127.0.0.1" in text
    assert "localhost" in text
    assert "[::1]" in text
