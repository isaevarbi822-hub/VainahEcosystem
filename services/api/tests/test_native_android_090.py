"""Native Android Messenger routing and credential integration contract."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ANDROID = ROOT / "apps/android/app"
SOURCE = ANDROID / "src/main/java/no/vainah/ecosystem"


def test_native_messenger_is_launched_without_webview():
    launcher = (SOURCE / "MainActivity.java").read_text(encoding="utf-8")
    native = (SOURCE / "NativeMessengerActivity.java").read_text(encoding="utf-8")
    manifest = (ANDROID / "src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert "BuildConfig.VAINAH_NATIVE_MESSENGER" in launcher
    assert "startActivity(new Intent(this, NativeMessengerActivity.class))" in launcher
    assert "NativeMessengerActivity" in manifest
    assert "new WebView(" not in native and "extends WebView" not in native
    assert "https://" not in native or "VAINAH_BASE_URL" in native


def test_google_is_native_and_server_verified():
    google = (SOURCE / "NativeGoogle.java").read_text(encoding="utf-8")
    client = (SOURCE / "NativeApi.java").read_text(encoding="utf-8")
    native = (SOURCE / "NativeMessengerActivity.java").read_text(encoding="utf-8")
    assert "CredentialManager.create(activity)" in google
    assert "GoogleIdTokenCredential.createFrom" in google
    assert '"/api/auth/google"' in native
    assert "AndroidKeyStore" in client
    assert "AES/GCM/NoPadding" in client
    assert "setInstanceFollowRedirects(false)" in client


def test_real_chat_data_and_no_fake_conversations():
    native = (SOURCE / "NativeMessengerActivity.java").read_text(encoding="utf-8")
    for route in ("/api/messenger/v2/chats", "/api/messenger/v2/thread/",
                  "/api/community/channels", "/api/community/bots"):
        assert route in native
    assert "Vainah пока не подключён" not in native
    assert "https://ваш-сервис.onrender.com" not in native

def test_native_messenger_091_groups_and_safe_navigation():
    native = (SOURCE / "NativeMessengerActivity.java").read_text(encoding="utf-8")
    gradle = (ANDROID / "build.gradle").read_text(encoding="utf-8")
    assert '"Создать группу"' in native
    assert 'new JSONArray(unique)' in native
    assert '"/api/messenger/v2/groups"' in native
    assert 'formatTime(c.optLong("updated_at"))' in native
    assert 'c.optInt("unread")' in native
    assert 'if(threadEpoch!=generation)return;' in native
    assert "stickToBottom" in native
    assert 'inDetail' in native
    assert "versionName '0.9.5'" in gradle


def test_native_092_usernames_and_invites():
    native = (SOURCE / "NativeMessengerActivity.java").read_text(encoding="utf-8")
    for marker in ("/api/people/username", "/api/people/search?q=", "/api/people/me",
                   "/api/community/channels/invitations", "/api/messenger/v2/groups/"):
        assert marker in native
    assert 'new JSONArray(unique)' in native

def test_native_messenger_093_design_and_apple_oauth():
    native = (SOURCE / "NativeMessengerActivity.java").read_text(encoding="utf-8")
    manifest = (ANDROID / "src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert 'showHome("contacts")' in native
    assert 'showHome("profile")' in native
    assert '"Личные","direct"' in native
    assert "Продолжить с Apple ID" in native
    assert "/api/auth/apple/start" in native
    assert "/api/auth/apple/exchange" in native
    assert 'android:scheme="vainah-messenger"' in manifest

def test_native_messenger_094_permanent_numeric_id():
    native = (SOURCE / "NativeMessengerActivity.java").read_text(encoding="utf-8")
    assert "numericId.setText(numeric)" in native
    assert 'ClipData.newPlainText("Vainah ID",number)' in native
    assert '"/api/people/id/"' in native
    gradle = (ANDROID / "build.gradle").read_text(encoding="utf-8")
    assert "versionName '0.9.5'" in gradle

def test_native_messenger_095_reliability_and_controls():
    native = (SOURCE / "NativeMessengerActivity.java").read_text(encoding="utf-8")
    network = (SOURCE / "NativeApi.java").read_text(encoding="utf-8")
    for marker in ("chatRefreshInProgress", "refreshRunning[0]",
                   "if(signature.equals(lastRendered[0]))return;",
                   "if(input.getText().toString().trim().equals(body))input.setText(\"\");",
                   "showChatOptions(contact,group)",
                   "/api/messenger/v2/preferences/",
                   "if(error!=null && !api.hasSession()",
                   "isOwner?\"Удалить группу\":\"Покинуть группу\""):
        assert marker in native, marker
    assert 'pair.startsWith("vainah_session=")' in network
