# Release history & roadmap

## 0.1.0 (prototype)
Vainah ID, notes, local dashboard.

## 0.2.0 (prototype)
Windows window runner, Android Studio WebView project, PWA shell.

## 0.3.0 (this source release)
- 11 functional **modules** in shared UI, 11 separate PWA manifests/entry points and icons, plus Windows launchers.
- Personal Messenger direct messages, private media library for photos/music, typed records for school tasks, calendar events, bookmarks and places.
- Open-Meteo weather and geocoding, OpenStreetMap map embeds, MyMemory translation.
- OpenAI-compatible AI gateway available **only when configured**.
- Expanded test coverage and Android file chooser.

## Production roadmap (not delivered)
1. Hosted, audited identity service with email verification, login protections, reset, OIDC and MFA; GDPR compliance / privacy controls.
2. Persistent PostgreSQL + migrations, encrypted backups, managed storage and quotas.
3. Messenger safety features, blocking/reporting, privacy options, realtime transport, e2e cryptography design.
4. Dedicated native browser app using a maintained browsing engine and a signed delivery pipeline.
5. AI provider configuration, consent, safeguards, budgets, caching and streaming.
6. Native notification service, offline synchronization and actual cross-device tests.
7. Signed Windows releases and verified Android APK/AAB, later iOS native client with Apple developer account.
