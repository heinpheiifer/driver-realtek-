import os
from pathlib import Path

from opentrader.old_app_static import (
    _is_engine_builtin_ui,
    resolve_old_app_static,
)


def test_skips_engine_builtin_ui(tmp_path, monkeypatch):
    old_root = tmp_path / "oldapp"
    static = old_root / "static"
    static.mkdir(parents=True)
    engine_index = static / "index.html"
    engine_index.write_text(
        "<html><title>Open Trader</title><button id='btnBookmapToggle'></button>"
        "<button id='runBacktestBtn'></button></html>",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENTRADER_OLD_APP", str(old_root))
    monkeypatch.delenv("OPENTRADER_USE_NEW_UI", raising=False)
    _, index = resolve_old_app_static()
    assert index is None


def test_finds_custom_old_ui(tmp_path, monkeypatch):
    old_root = tmp_path / "oldapp"
    static = old_root / "static"
    static.mkdir(parents=True)
    custom = static / "index.html"
    custom.write_text(
        "<html><title>Heinz Chart</title><canvas id='heikinChart'></canvas></html>",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENTRADER_OLD_APP", str(old_root))
    monkeypatch.delenv("OPENTRADER_USE_NEW_UI", raising=False)
    static_dir, index = resolve_old_app_static()
    assert static_dir == static
    assert index == custom


def test_index_override(tmp_path, monkeypatch):
    old_root = tmp_path / "oldapp"
    old_root.mkdir()
    custom = tmp_path / "mychart.html"
    custom.write_text("<html>custom</html>", encoding="utf-8")
    monkeypatch.setenv("OPENTRADER_OLD_APP", str(old_root))
    monkeypatch.setenv("OPENTRADER_UI_INDEX", str(custom))
    monkeypatch.delenv("OPENTRADER_USE_NEW_UI", raising=False)
    static_dir, index = resolve_old_app_static()
    assert index == custom.resolve()
    assert static_dir == custom.parent.resolve()


def test_is_engine_builtin_ui_detects_git_ui(tmp_path):
    path = tmp_path / "index.html"
    path.write_text(
        "Open Trader btnBookmapToggle runBacktestBtn",
        encoding="utf-8",
    )
    assert _is_engine_builtin_ui(path) is True
