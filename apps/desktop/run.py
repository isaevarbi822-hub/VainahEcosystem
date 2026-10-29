"""Vainah Ecosystem desktop: starts local API and opens a native application window.
Run from the repository root with: python apps/desktop/run.py
The local server is bound exclusively to 127.0.0.1.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
import json

APP_NAMES = ("ai", "messenger", "browser", "music", "weather", "maps", "notes", "translate", "study", "photos", "calendar")


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    directory = base / "Vainah" / "Ecosystem"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def allocate_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def launch() -> None:
    parser = argparse.ArgumentParser(description="Vainah Ecosystem desktop app")
    parser.add_argument("--browser", action="store_true", help="Use the system browser instead of native WebView")
    parser.add_argument("--app", choices=APP_NAMES, help="Open a named Vainah app instead of the main launcher")
    args = parser.parse_args()

    store = app_data_dir()
    # Persistent, writable per-user database even when launched from a read-only packaged executable.
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + (store / "vainah.db").as_posix())
    os.environ.setdefault("VAINAH_UPLOAD_DIR", str(store / "uploads"))
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("COOKIE_SECURE", "false")  # local loopback only

    configured_url = (os.environ.get("VAINAH_BASE_URL") or "").strip().rstrip("/")
    config_path = store / "server-url.txt"
    if not configured_url and config_path.exists():
        configured_url = config_path.read_text(encoding="utf-8").strip().rstrip("/")
    if configured_url:
        from urllib.parse import urlsplit
        parsed = urlsplit(configured_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query or parsed.path not in ("", "/"):
            raise ValueError("Vainah server-url.txt: укажите только HTTPS-адрес Render, без пути и параметров")
        target = configured_url + (f"/app/{args.app}" if args.app else "")
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("Для окна Vainah установите pywebview") from exc
        if args.browser:
            webbrowser.open(target)
            return
        webview.create_window("Vainah " + (args.app.title() if args.app else "Ecosystem"), target,
                              width=1200, height=820, min_size=(780, 560), background_color="#0b101b")
        webview.start(private_mode=False, storage_path=str(store / "webview-profile"))
        return

    from services.api.app.main import app
    import uvicorn

    # Reuse a Vainah server already running on loopback so users can open multiple app windows.
    # An unrelated process on the port is rejected. We never bind 0.0.0.0.
    port = 8000
    url = f"http://127.0.0.1:{port}"
    own_server = False
    server = None
    thread = None
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
            free = True
        except OSError:
            free = False
    if not free:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=2) as resp:
                info = json.load(resp)
                if info.get("product") != "Vainah Ecosystem" or info.get("version") != "0.6.0":
                    raise RuntimeError("На порту 8000 работает другая версия сервера")
        except (OSError, ValueError) as exc:
            raise RuntimeError("Порт 8000 занят другой программой. Закройте её.") from exc
    else:
        own_server = True
        config = uvicorn.Config(app, host="127.0.0.1", port=port,
                                log_level="warning", access_log=False)
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, name="vainah-api", daemon=True)
        thread.start()
        for _ in range(100):
            if not thread.is_alive():
                raise RuntimeError("Локальный сервер Vainah не запустился")
            try:
                with urllib.request.urlopen(url + "/api/health", timeout=0.3) as resp:
                    if resp.status == 200:
                        break
            except (OSError, TimeoutError):
                time.sleep(0.08)
        else:
            server.should_exit = True
            raise RuntimeError("Приложение не смогло запустить внутренний сервер")
    url += f"/app/{args.app}" if args.app else ""

    try:
        if args.browser:
            webbrowser.open(url)
            input("Vainah запущен. Нажмите Enter для выхода...\n")
        else:
            try:
                import webview
            except ImportError as exc:
                raise RuntimeError("Установите desktop-зависимости: pip install -r requirements-desktop.txt") from exc
            webview.create_window("Vainah " + (args.app.title() if args.app else "Ecosystem"), url, width=1200, height=820,
                                  min_size=(780, 560), background_color="#0b101b")
            webview.start(private_mode=False, storage_path=str(store / "webview-profile"))
    finally:
        if own_server and server is not None and thread is not None:
            server.should_exit = True
            thread.join(timeout=4)


if __name__ == "__main__":
    # When frozen by PyInstaller the package modules live in the bundle. When run from source
    # make the project root importable without installing the package first.
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    launch()
