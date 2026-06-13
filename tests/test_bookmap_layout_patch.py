import subprocess
from pathlib import Path


def test_patch_script_injects_bookmap_css(tmp_path):
    root = Path(__file__).resolve().parents[1]
    chart_root = tmp_path / "OpenTrader"
    static = chart_root / "static"
    static.mkdir(parents=True)
    index = static / "index.html"
    index.write_text(
        "<html><head><title>Open Trader</title></head><body></body></html>",
        encoding="utf-8",
    )

    subprocess.run(
        ["bash", str(root / "scripts/patch_bookmap_below_chart.sh"), str(chart_root)],
        check=True,
        capture_output=True,
        text=True,
    )

    text = index.read_text(encoding="utf-8")
    assert "chart_patch/bookmap_below_chart.css" in text
    assert "chart_patch/bookmap_layout.js" in text
    assert (static / "chart_patch/bookmap_below_chart.css").is_file()
    assert (static / "chart_patch/bookmap_layout.js").is_file()


def test_patch_assets_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "opentrader/chart_patches/bookmap_below_chart.css").is_file()
    assert (root / "opentrader/chart_patches/bookmap_layout.js").is_file()
    assert (root / "scripts/patch_bookmap_below_chart.sh").is_file()
