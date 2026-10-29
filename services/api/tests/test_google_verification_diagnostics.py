"""Google verification diagnostics tests (no network requests)."""
import sys
from types import ModuleType

import pytest
from fastapi import HTTPException

from services.api.app import google_identity


def _fake_google(monkeypatch, verify):
    modules = {name: ModuleType(name) for name in (
        "google", "google.auth", "google.auth.exceptions",
        "google.auth.transport", "google.auth.transport.requests",
        "google.oauth2", "google.oauth2.id_token")}
    modules["google.auth.exceptions"].TransportError = type("TransportError", (Exception,), {})
    modules["google.auth.transport.requests"].Request = lambda: "stub request"
    modules["google.oauth2.id_token"].verify_oauth2_token = verify
    modules["google.auth.transport"].requests = modules["google.auth.transport.requests"]
    modules["google.oauth2"].id_token = modules["google.oauth2.id_token"]
    modules["google.auth"].exceptions = modules["google.auth.exceptions"]
    modules["google.auth"].transport = modules["google.auth.transport"]
    modules["google"].auth = modules["google.auth"]
    modules["google"].oauth2 = modules["google.oauth2"]
    for name, mod in modules.items():
        monkeypatch.setitem(sys.modules, name, mod)
    return modules["google.auth.exceptions"].TransportError


def test_valid_id_token_is_accepted(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test.apps.googleusercontent.com")
    def verify(token, request, audience):
        assert audience == "test.apps.googleusercontent.com"
        return {"iss": "https://accounts.google.com", "email_verified": True,
                "sub": "google-sub", "email": "EXAMPLE@google.com", "name": "Tester"}
    _fake_google(monkeypatch, verify)
    assert google_identity.verify_google_credential("a" * 40) == {
        "sub": "google-sub", "email": "example@google.com", "name": "Tester"}


def test_wrong_audience_is_safe_to_display(monkeypatch, caplog):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test.apps.googleusercontent.com")
    def verify(*args):
        raise ValueError("Token has wrong audience private-google-identifier")
    _fake_google(monkeypatch, verify)
    with pytest.raises(HTTPException) as response:
        google_identity.verify_google_credential("a" * 40)
    assert response.value.status_code == 401
    assert "Client ID" in response.value.detail
    assert "private-google-identifier" not in caplog.text


def test_google_network_failure_is_not_misreported_as_bad_token(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test.apps.googleusercontent.com")
    def verify(*args):
        raise google_transport_error("certificate fetch failed")
    google_transport_error = _fake_google(monkeypatch, verify)
    with pytest.raises(HTTPException) as response:
        google_identity.verify_google_credential("a" * 40)
    assert response.value.status_code == 503


def test_missing_google_transport_dependency(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test.apps.googleusercontent.com")
    import builtins
    native_import = builtins.__import__
    def missing_dependency(name, *args, **kwargs):
        if name == "google.auth.exceptions":
            raise ImportError("requests library is not installed")
        return native_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", missing_dependency)
    with pytest.raises(HTTPException) as response:
        google_identity.verify_google_credential("a" * 40)
    assert response.value.status_code == 503
    assert "библиотеки" in response.value.detail
