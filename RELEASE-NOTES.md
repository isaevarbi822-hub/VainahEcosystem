# Vainah Ecosystem v0.4.0 — Private preview improvements

Released: 2026-10-29 (source preview only).

## Added and improved
- Vainah ID: editable display name, password change, session revocation, optional signup invitation code, basic single-process rate limit.
- Neon: PostgreSQL-backed private media blobs for files saved on Render, selectable with `VAINAH_MEDIA_BACKEND=database`. Existing file-based records remain readable where their files exist.
- Health endpoint verifies a database connection, returning 503 if unavailable.
- UI: profile settings, application search, mobile bottom navigation, unsaved-note confirmation, Ctrl+S.
- Render blueprint + deployment documentation and 5 new regression tests.
- Android project version updated to 0.4.0 (source, not compiled APK).

## Validation
- Python integration tests: 31 passed in authoring environment.
- JavaScript modules: Node syntax check passed.
- Browser GUI automation unavailable: headless Chromium blocked navigation in this environment.
- Windows EXE and Android APK compilation NOT executed here.
- Neon production database connectivity has NOT been verified using user's live credentials.

## Remaining production blockers
- Email verification and recovery, scalable abuse protection, proper schema migrations, secure object storage, privacy policy, moderation/block controls for Messenger, full standalone browser engine and native app packaging/signing.

---

# Vainah Ecosystem 0.3.0 — 29 October 2026

### Source release available
- 11 integrated app sections with common Vainah ID.
- Separate PWA installation entry points and unique icons for each section.
- Eleven Windows `.bat` app launchers and one pywebview desktop host (requires Python).
- Android Studio project: WebView client with native photo/music file picker (requires Android SDK, server; not APK).
- SQLite/PostgreSQL data models, Messenger, personal uploads, bookmark/calendar/study/places data, weather/map/translate integrations, optional AI gateway.
- 26 automated API tests pass in this environment.

### Not claimed completed
- Windows .exe / signed installer and Android .apk: not built or tested on target operating systems.
- AI requires configured external or self-hosted model API.
- Browser provides bookmarks and external launch; no built-in browsing engine.
- No public identity security audit, moderation, E2EE, mobile push, offline data sync, or public Internet deployment.
- UI browser automated test could not run due to browser environment restrictions; JavaScript syntax validated with Node.js and API endpoints tested.

For local educational development only. Do not add live users before security/privacy work and appropriate testing.
