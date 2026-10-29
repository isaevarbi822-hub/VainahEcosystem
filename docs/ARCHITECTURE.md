# Vainah Ecosystem — architecture (0.3.0)

## Architecture

We use a modular monolith for the prototype. Client apps use the same origin for UI and API, so the local HttpOnly session cookie can be reused safely inside the first-party app. No credentials are shared with external services.

```text
Windows desktop window ─┐
Android WebView wrapper ─┼── Vainah FastAPI server ─── Vainah ID ─── SQLAlchemy ─── SQLite / PostgreSQL
Web/PWA (11 entries) ────┘          ├── Notes
                                   ├── Messenger
                                   ├── App records (Calendar / Study / Maps / Browser / Playlists)
                                   ├── Private media (Music / Photos) ─── local file store
                                   └── Optional provider APIs (Weather / Translate / AI)
```

### Vainah ID

- User identity is a UUID. Every persisted item is user-scoped using the server-derived `user.id`, not client-controlled `user_id`.
- Passwords use Argon2id hashes; sessions have unpredictable cookie tokens stored as hashes, 14-day expiry, HttpOnly / SameSite Strict cookies, and CSRF tokens required for authenticated writes.
- Local loopback development only. Production requires verified identities, managed OIDC authorization-code + PKCE for independent app origins, password recovery, rate limiting, 2FA, user deletion, role review, and security/abuse controls.
- Existing VainahVPN credentials are **not** imported; no secrets are shipped.

### Data models

| Table | Owner | Purpose |
|---|---|---|
| users, login_sessions | ID | Accounts / sessions |
| notes | Notes | Text notes |
| app_records | Calendar/Study/Browser/Maps/Playlists | User-scoped typed JSON records |
| direct_messages | Messenger | Sender, recipient, message |
| private_media | Music/Photos | Metadata and media owner |

Uploaded files are saved to `VAINAH_UPLOAD_DIR` or local `data/uploads/{user_id}/{uuid}`. A new version should move to object storage with antivirus/image processing and per-account quotas. File endpoints are authenticated, checks run by ownership, and PNG/JPEG/GIF/WebP and common audio magic bytes are validated. More comprehensive media inspection is needed before public release.

### External integrations

- Weather and city lookup: Open-Meteo. User searches and coordinates leave the server for this explicit lookup.
- Maps display: OpenStreetMap embed. Browser fetches map tiles from the external site.
- Translate: MyMemory API. Submitted text is sent to MyMemory; UI warns before submission. Its terms, availability and free limits apply.
- AI: operator-configured OpenAI-compatible HTTPS endpoint and model. User prompt is sent to that provider; no built-in model or fake AI responses. Require cost limits, moderation and privacy agreements before public use.

### Current limitations

- Messenger polling instead of WebSocket delivery; no push, blocking/reporting, E2EE, voice/video, or moderation.
- Browser is a *bookmark manager* and external URL launcher, **not** a native browsing engine.
- Music is a personal audio library, not a streaming music catalog.
- Calendar does not integrate with OS notification providers.
- All PWA app entries share a single origin and session; they are separate launchers, not isolated OIDC apps.
- Android wrapper needs a reachable running FastAPI service. No mobile local Python API is bundled into the APK.
- Database uses `create_all` for local MVP upgrades; production needs Alembic migrations.

## Requirements for public release

1. Choose an identity platform / implement OIDC, email verification, recovery, MFA, anti-brute-force, delete and export.
2. Introduce persistent per-user and per-IP rate limits (auth, messaging, AI, translation, uploads), abuse report/block, and youth safety settings.
3. Review external data processors, licensing, logs, retention, Norwegian/EU privacy requirements; obtain any required consents.
4. Deploy behind HTTPS with `ENVIRONMENT=production`, `COOKIE_SECURE=true`, exact `APP_ORIGIN=https://...`, secrets in the deployment provider's secure settings.
5. PostgreSQL with backups, Alembic migrations, monitoring, alerts, transactional email, storage limits, CDN/object storage where warranted.
6. Independent security code audit, authentication/session penetration testing and validation on actual Windows/Android devices before any public account registrations.
7. Separate release pipelines for signed Windows MSI/EXE and Android APK/AAB; Android SDK and Windows runtime needed for these builds.

**Security boundary:** No production guarantees until those changes and independent verification are complete.


## 0.4 storage upgrade

`private_media` stores metadata. New table `private_media_blobs` stores binary content when `VAINAH_MEDIA_BACKEND=database` or the SQLAlchemy backend is PostgreSQL. This avoids Render ephemeral file loss but increases Neon quota usage. Existing filesystem media reads still work if the original file is present. `create_all()` creates the new table; Alembic migrations are required before production. The service has no automatic local-to-Neon media import.

Account settings use CSRF and origin checks. Password changes invalidate other login sessions. Registration can be gated with `VAINAH_SIGNUP_CODE`. The built-in limiter is process-local, so a public multi-worker deployment needs central rate limiting. No account email verification or password recovery is provided.
