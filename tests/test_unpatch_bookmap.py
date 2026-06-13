import subprocess
from pathlib import Path


def test_unpatch_removes_bookmap_injections(tmp_path):
    root = Path(__file__).resolve().parents[1]
    chart = tmp_path / "OpenTrader"
    dist = chart / "frontend" / "dist"
    dist.mkdir(parents=True)
    index = dist / "index.html"
    index.write_text(
        "<html><head>"
        '<link rel="stylesheet" href="./chart_patch/bookmap_below_chart.css" />'
        '<script src="./chart_patch/bookmap_layout.js" defer></script>'
        '<style id="ot-bookmap-below-inline">.x{}</style>'
        "</head><body></body></html>",
        encoding="utf-8",
    )

    subprocess.run(
        ["bash", str(root / "scripts/unpatch_bookmap.sh"), str(chart)],
        check=True,
        capture_output=True,
        text=True,
    )

    text = index.read_text(encoding="utf-8")
    assert "bookmap_below_chart" not in text
    assert "bookmap_layout" not in text
    assert "ot-bookmap-below-inline" not in text
    assert "<head></head>" in text or "</head>" in text
