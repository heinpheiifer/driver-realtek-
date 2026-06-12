from pathlib import Path

from trading.blackbull_mt5 import sync_wine_mt5_exports


def test_sync_wine_mt5_exports(tmp_path, monkeypatch):
    wine_files = tmp_path / "wine" / "MQL5" / "Files" / "blackbull_import"
    wine_files.mkdir(parents=True)
    csv = wine_files / "xrpusd_m1.csv"
    csv.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-06-11 12:00:00,2.1,2.2,2.0,2.15,1000\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "trading.blackbull_mt5.find_wine_mt5_files_dirs",
        lambda: [wine_files.parent],
    )

    result = sync_wine_mt5_exports(dest_root=tmp_path / "engine")
    assert result["count"] >= 1
    imported = tmp_path / "engine" / "trading_data" / "blackbull_import" / "xrpusd_m1.csv"
    assert imported.is_file()
