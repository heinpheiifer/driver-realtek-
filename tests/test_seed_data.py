from pathlib import Path

from trading.seed_data import ensure_seed_data, find_seed_file


def test_ensure_seed_data(tmp_path):
    seed_root = Path(__file__).resolve().parents[1] / "seeds" / "chart"
    if not seed_root.is_dir():
        return
    result = ensure_seed_data(dest_root=tmp_path)
    assert (tmp_path / "trading_data" / "blackbull_import" / "xrpusd_m1.csv").is_file()
    assert result["count"] >= 1


def test_find_seed_xrpusd():
    path = find_seed_file("XRPUSD", "M1")
    assert path is not None
    assert path.name == "xrpusd_m1.csv"
