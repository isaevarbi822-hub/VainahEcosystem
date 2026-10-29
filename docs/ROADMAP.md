# Release history & roadmap

## 0.1.0 (prototype)
Vainah ID, notes, local dashboard.

## 0.2.0 (prototype)
Windows window runner, Android Studio WebView project, PWA shell.

## 0.3.0 (earlier preview)
- 11 functional **modules** in shared UI, 11 separate PWA manifests/entry points and icons, plus Windows launchers.
- Personal Messenger direct messages, private media library for photos/music, typed records for school tasks, calendar events, bookmarks and places.
- Open-Meteo weather and geocoding, OpenStreetMap map embeds, MyMemory translation.
- OpenAI-compatible AI gateway available **only when configured**.
- Expanded test coverage and Android file chooser.

## 0.7.0 (current private preview)
- Same-origin, session-authenticated WebSocket live updates (single worker only).
- Experimental one-to-one audio/video call signalling via WebRTC with browser permissions; no TURN relay or background incoming calls.
- Opt-in browser notifications only when Messenger remains open; no Android native push.
- Video capture permission gated for Android WebView.

## Production roadmap (not delivered)
1. Hosted, audited identity service with email verification, login protections, reset, OIDC and MFA; GDPR compliance / privacy controls.
2. Persistent PostgreSQL + migrations, encrypted backups, managed storage and quotas.
3. Messenger safety features, blocking/reporting, privacy options, distributed realtime pub/sub, E2E cryptography design, production TURN infrastructure.
4. Dedicated native browser app using a maintained browsing engine and a signed delivery pipeline.
5. AI provider configuration, consent, safeguards, budgets, caching and streaming.
6. Native notification service, offline synchronization and actual cross-device tests.
7. Signed Windows releases and verified Android APK/AAB, later iOS native client with Apple developer account.
