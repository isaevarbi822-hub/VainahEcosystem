"""Regression checks for frozen Windows GUI apps (no stdout/stderr)."""
import logging
import sys

from apps.desktop.run import create_embedded_server


def test_embedded_server_works_without_console(monkeypatch, tmp_path):
    async def fake_app(scope, receive, send):
        pass

    # PyInstaller --windowed has no console streams on Windows.
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "stdout", None)
    server = create_embedded_server(fake_app, tmp_path, 18000)
    assert server.config.log_config is None
    assert server.config.port == 18000
    assert server.config.host == "127.0.0.1"
    logging.getLogger("uvicorn.error").warning("GUI regression test")
    assert "GUI regression test" in (tmp_path / "vainah-desktop.log").read_text(encoding="utf-8")
