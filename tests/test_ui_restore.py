from pathlib import Path

from opentrader.ui_restore import ensure_old_ui_restored


def test_restore_from_backup_when_engine_ui_present(tmp_path, monkeypatch):
    old_root = tmp_path / "oldapp"
    static = old_root / "static"
    static.mkdir(parents=True)

    # Simulate overwritten UI (git engine)
    (static / "index.html").write_text(
        "Open Trader btnBookmapToggle runBacktestBtn",
        encoding="utf-8",
    )

    backup_base = old_root / ".opentrader_ui_backup" / "20260101_120000"
    bstatic = backup_base / "static"
    bstatic.mkdir(parents=True)
    (bstatic / "index.html").write_text(
        "<html><title>Heinz Chart</title><canvas id='heikin'></canvas></html>",
        encoding="utf-8",
    )
    (old_root / ".opentrader_ui_backup" / "latest").symlink_to("20260101_120000")

    monkeypatch.setenv("OPENTRADER_OLD_APP", str(old_root))
    monkeypatch.delenv("OPENTRADER_USE_NEW_UI", raising=False)
    result = ensure_old_ui_restored()

    assert result["restored"] is True
    restored_index = old_root / "static" / "index.html"
    assert "Heinz Chart" in restored_index.read_text(encoding="utf-8")
