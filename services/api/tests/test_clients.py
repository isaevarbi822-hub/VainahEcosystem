import json
from pathlib import Path
from fastapi.testclient import TestClient
from services.api.app.main import create_app

ROOT = Path(__file__).resolve().parents[3]


def test_android_install_metadata(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'mobile.db'}")
    with TestClient(app) as client:
        manifest = client.get('/manifest.webmanifest')
        assert manifest.status_code == 200
        assert manifest.headers['content-type'].startswith('application/manifest+json')
        data = manifest.json()
        assert data['display'] == 'standalone'
        assert len(data['icons']) == 2
        assert client.get('/assets/icon-192.png').status_code == 200
        worker = client.get('/sw.js')
        assert worker.status_code == 200
        assert "startsWith('/api/')" in worker.text
        assert worker.headers['cache-control'] == 'no-cache'
        assert 'rel="manifest"' in client.get('/').text
    app.state.engine.dispose()


def test_android_project_source_guardrails():
    base = ROOT / 'apps/android'
    manifest = (base / 'app/src/main/AndroidManifest.xml').read_text()
    main = (base / 'app/src/main/java/no/vainah/ecosystem/MainActivity.java').read_text()
    assert 'android.permission.INTERNET' in manifest
    assert 'android:allowBackup="false"' in manifest
    assert 'handler.cancel()' in main
    assert 'setAcceptThirdPartyCookies(webView, false)' in main
    assert 'sameOrigin' in main


def test_desktop_data_directory_and_local_only(monkeypatch, tmp_path):
    import importlib.util
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path))
    spec = importlib.util.spec_from_file_location('vainah_desktop', ROOT / 'apps/desktop/run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    location = module.app_data_dir()
    assert location == tmp_path / 'Vainah' / 'Ecosystem'
    assert location.is_dir()
    assert 1 <= module.allocate_local_port() <= 65535
    assert '127.0.0.1' in (ROOT / 'apps/desktop/run.py').read_text()
