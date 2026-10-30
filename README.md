# Vainah Messenger — current Android build (0.10.1)

This repository contains Vainah Messenger and the wider Vainah Ecosystem app suite. The Messenger Android package is a native app built around `NativeMessengerActivity`; the separate Ecosystem APK remains a WebView app. The Messenger connects to the deployed Vainah API over HTTPS.

The current Android source includes direct and group chats, attachments, voice messages, short video notes, and media previews. Device-specific camera, playback, and sign-in behavior still requires real-device testing. The server may encrypt message bodies at rest when configured, but that is **not end-to-end encryption**; attachments are not covered by that setting. Android background push and background calls are not implemented.

## Current build instructions

Use the existing repository and the GitHub Actions workflow documented in [MESSENGER-BUILD.md](MESSENGER-BUILD.md). Android configuration and signing setup are documented in [apps/android/NATIVE-MESSENGER-SETUP.md](apps/android/NATIVE-MESSENGER-SETUP.md). For current Messenger builds, use the linked workflow guide; the 0.7–0.8 sections below are historical.

 > The older 0.7–0.8 sections below are retained as release history. Their version numbers, limitations, and commands are historical, not the current build guide.

---

# Vainah Messenger 0.8.1 — Mobile UI and server setup

- New Android-friendly conversation list matching the approved Vainah design: bottom navigation, rounded initials/channel/bot avatars, search and compose.
- Chat list now integrates actual subscribed channels and bots; it never inserts fictional conversations.
- Android allows configuring a real HTTPS server URL in app settings when the build has no preset VAINAH_BASE_URL. No more default localhost dead end.
- Installable files are only confirmed after GitHub Actions finishes successfully. Google native sign-in still not implemented.

# Vainah Messenger 0.8.0 — standalone preview

**Новый сайт Messenger** запускается по `/` или `/app/messenger`. На нём больше нет каталога 11 приложений и Google-кнопки. Остальные приложения Vainah остаются в кодовой базе и доступны через собственные маршруты.

### Что реализовано

- Крупный адаптивный веб-сайт и самостоятельный интерфейс Vainah Messenger с оригинальными SVG-иконками и навигацией по чатам, каналам, ботам и профилю.
- Вход и регистрация по email и паролю. Для немедленной регистрации без кода приглашения в Render требуется **`VAINAH_SIGNUP_MODE=open`**. Для приватного режима оставьте закрытую регистрацию и задайте `VAINAH_SIGNUP_CODE`.
- Публичный каталог каналов для авторизованных пользователей; подписки и публикации владельца.
- Простейшие боты с ответами на ключевые слова. Это не Telegram Bot API и не система выполнения внешнего кода.
- Анимированная галочка **«Проверено Vainah»**, доступная только при проверке администратором. Чтобы выбрать администраторов, укажите через запятую их UUID из настроек профиля в `VAINAH_VERIFICATION_ADMIN_IDS`.
- CSS учитывает `prefers-reduced-motion`: пользователи с отключённой анимацией не видят пульсацию галочки.

### Android и Windows

- Android-проект по-прежнему собирается через GitHub Actions: `.github/workflows/build-installers.yml`.
- После неудачной Android-сборки скачайте artifact **`Vainah-Android-build-diagnostics`**. Его лог `android-ci-logs/ecosystem.log` или `messenger.log` содержит исходную ошибку Gradle.
- Java 17 и Gradle 9.6 соответствуют Android Gradle Plugin 9.4.
- **Готовый APK ещё не подтверждён**. Android Google Credential Manager и безопасная передача сессии в WebView пока не реализованы. Google-вход в браузере был убран из Messenger по пожеланию пользователя; вход по email продолжает работать. Для нативного Google-входа будет нужна отдельная реализация на Android и Windows.
- Для EXE и APK требуется настроенный HTTPS URL Render (`VAINAH_BASE_URL`) и успешная сборка. На бесплатном Render ограничены ресурсы.

### Перед публичным запуском

Email пока не подтверждается ссылкой или кодом. Для открытой регистрации нужны защита от массового создания аккаунтов, подтверждение адреса и инструменты модерации. Каналы/боты и звонки — тестовые реализации. Сквозного шифрования нет, а фоновые push-уведомления не завершены.

---

> **Messenger 0.7.0:** authenticated WebSocket for foreground real-time updates; opt-in foreground browser alerts; experimental one-to-one WebRTC audio/video calling with own call controls. Calls require BOTH users to keep Messenger open on the same server worker, HTTPS, microphone/camera permission, and a compatible browser. ICE uses public STUN, **no TURN relay**: some internet/mobile networks will not connect. No Android push or always-on calling. Messages are still stored server-side and have no end-to-end encryption. See RELEASE-NOTES.md.

> **Messenger 0.7.0:** обновлены диалоги, реакции, вложения, блокировка и отдельные точки сборки EXE/APK. Подробности: [MESSENGER-BUILD.md](MESSENGER-BUILD.md) и [RELEASE-NOTES.md](RELEASE-NOTES.md). Сообщения НЕ имеют сквозного шифрования.

# Vainah Ecosystem — 0.7.0 App Suite (development preview)

**Eleven interactive app modules, one Vainah ID** — a Python FastAPI backend, a responsive web/PWA shell, a Windows desktop launcher, and an Android Studio WebView wrapper. The project is a working **local multi-app preview**, **not** eleven independently compiled native products and **not** yet production-ready. The native Windows EXE and Android APK must be built on compatible development machines; this ZIP contains their source projects.

## Messenger 0.7.0 (private preview)

- Private **group conversations** for up to 25 Vainah ID accounts, with owner-only invitations, member lists, leave and owner-delete controls.
- Personal chat preferences: **pin, archive and mute**. These settings are stored in the database per account.
- **Quoted replies**, **search in direct conversations**, chat filtering and better responsive navigation.
- Browser microphone recording of short **WebM/OGG voice messages** (only where the device grants microphone permission), plus image and audio attachments in direct chats.
- Android client gates microphone and camera use with runtime permissions and a same-origin check.
- Existing messages and Vainah ID accounts are kept. New tables are additive.
- Messaging is **not end-to-end encrypted**. Group chats are currently text-only; attachments, voice and reactions are supported in direct chats. Experimental live calls and single-worker realtime are included in 0.7.0; stories, reliable public calling, background push and production-scale realtime remain future work.

## Account and platform improvements (0.4–0.7)

- Vainah ID now has a **Settings** screen: change display name, update password and revoke sessions on other devices.
- Optional `VAINAH_SIGNUP_CODE` restricts registration for a small private beta, without exposing the code in source code.
- The single-worker preview includes a basic rate limiter on failed logins and registration; this is not a replacement for distributed abuse protection.
- **Neon/PostgreSQL media persistence:** photos and audio now use an optional database-backed binary store so uploads do not disappear when Render's ephemeral disk resets. PostgreSQL defaults to database storage; SQLite/local Windows defaults to filesystem storage. Old filesystem items are still readable where files exist.
- Check database connectivity in `/api/health`; automatic Render health checks can fail when the database is unavailable.
- Add a searchable app catalog (`Ctrl+K`), responsive bottom navigation on phones, unsaved-note warnings and `Ctrl+S` note saving.
- A `render.yaml` blueprint is included for a private technical preview.

## What you can use now

| Application | Available in the 0.7.0 preview | Scope / limitations |
|---|---|---|
| Vainah ID | Local registration, login, profile/password changes, logout and revoking other sessions | Unverified email; no recovery/MFA; basic per-process limiter only — private beta tests |
| Notes | Personal note creation, editing, search, deletion | Stored in SQLite/PostgreSQL with unsaved-edit confirmation |
| Messenger | Direct messages, text groups, reactions, attachments, voice notes, pin/archive/mute, WebSocket live updates and experimental WebRTC audio/video calls | No end-to-end message encryption, TURN, native background push or group file attachments; calls may fail on restrictive networks |
| Browser | Bookmarks with external URL opening | Not a standalone Chromium/Firefox browser engine |
| Music | Upload and play private MP3/WAV/OGG/M4A files | No licensed streaming catalog; 20 MB/file and database storage quota considerations |
| Weather | City search and 5-day forecast | Requires Internet and Open-Meteo access |
| Maps | Map, city lookup, save personal places | Requires Internet and OpenStreetMap/Open-Meteo; not turn-by-turn navigation |
| Translate | Translate short phrases across 10 languages | Requires Internet; user-submitted text is sent to MyMemory |
| Study | Private school task CRUD and completion tracking | No school-system integration |
| Photos | Private upload, view and delete photos | Limit 8 MB/file; PostgreSQL binary storage or local filesystem; no automatic recognition |
| Calendar | Add, edit and remove dated events | No OS notifications or calendar provider sync |
| AI | Chat frontend and configurable OpenAI-compatible API backend | **No built-in model**; needs 3 environment variables and a provider |

> The 11 installable PWA entries share the **same** code, server and login system. On supported browsers, each has a distinct app manifest/icon at `/app/{app}`. They are not 11 standalone APK/EXE files.

## Run on Windows

1. Install Python 3.12+.
2. Extract this project into a new folder.
3. Double-click **`start-windows.bat`**. It installs the Python dependencies into `.venv`, runs an API on `127.0.0.1:8000`, and opens a **separate desktop application window** using pywebview.
4. Create a **throwaway test account with a unique password**.
5. To open a specific app in its own window, use `apps/desktop/launchers/Vainah-AI.bat`, `Vainah-Notes.bat`, and the other eleven launchers. They reuse the same running API.
6. For an EXE build on Windows, run **`build-windows-exe.bat`**. This has not been compiled on Windows in the authoring environment.

If you prefer browser development:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open http://127.0.0.1:8000, register and explore. Windows desktop uses your local application data path for its account DB and uploads, so it can write files even when installed in Program Files.

## Deploy a private preview to Render + Neon

1. Upload this project into a **separate** GitHub repository (do not upload the ZIP itself). The root of the repository must contain `requirements.txt`, `render.yaml`, `apps/` and `services/`.
2. In Render, create a **Web Service**, choose this repository, use Python, the build command `pip install -r requirements.txt` and the start command `uvicorn services.api.app.main:app --host 0.0.0.0 --port $PORT`. Alternatively, use the `render.yaml` blueprint.
3. Configure the environment variables in **Render → Environment**, not in GitHub:
   - `DATABASE_URL`: **Neon pooled connection string** copied from your *separate* Vainah Ecosystem project (do not post this URL publicly).
   - `APP_ORIGIN`: your precise HTTPS Render URL, e.g., `https://YOUR-SERVICE.onrender.com`, **no trailing slash**.
   - `COOKIE_SECURE=true`, `ENVIRONMENT=production`.
   - `VAINAH_SIGNUP_CODE`: a long random string that you keep private and enter on the registration form to test your own private account.
   - `VAINAH_MEDIA_BACKEND=database`: stores uploads in the PostgreSQL database rather than ephemeral Render disk.
4. Deploy and open `https://YOUR-SERVICE.onrender.com/api/health`. A working database should return `status: ok` and `database: connected`.
5. Open the main page, register with the invitation code and create a test note. Test login from a second device only with throwaway credentials.

**Limitations:** This is still NOT a public identity service: no email verification or password recovery, no end-to-end encrypted messaging, no distributed abuse limiter or external media storage; automatic schema creation is not a migration framework. Database-backed media consumes Neon database storage, so do not upload a large library. A separate object store and security review are needed for a real release.

## Android packages

The repository builds two separate APKs: the native Vainah Messenger and the older WebView-based Vainah Ecosystem app. The Messenger APK requires a reachable HTTPS API; it does not serve the backend itself. For current workflow artifact names and setup requirements, see [MESSENGER-BUILD.md](MESSENGER-BUILD.md) and [native Android setup](apps/android/NATIVE-MESSENGER-SETUP.md). A successful CI build does not replace sign-in, camera, media, or network testing on a physical device.

## Eleven separately installable PWA entry points

After hosting on HTTPS, visit `/app/ai`, `/app/messenger`, `/app/browser`, `/app/music`, `/app/weather`, `/app/maps`, `/app/notes`, `/app/translate`, `/app/study`, `/app/photos`, or `/app/calendar`. Each route advertises a unique PWA manifest and icon. Where supported, the browser install menu can add that entry point to your home screen/start menu. The account and API are shared. PWA support varies by browser and platform.

## AI model configuration (optional)

The code intentionally does **not** contain an API key. In an operator-controlled deployment, set:

```text
VAINAH_AI_BASE_URL=https://your-compatible-ai-api.example/v1
VAINAH_AI_API_KEY=set-on-server-not-in-git
VAINAH_AI_MODEL=your-model-name
```

This is an OpenAI-compatible `/chat/completions` API integration, not a claim of a privately trained Vainah model. The user prompt will be sent to the selected provider. Use a model/provider with appropriate data handling and budget controls before inviting other users.

## Run tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Test coverage includes identity, cookie/CSRF behavior, Notes CRUD, Calendar/Study/Bookmark/Place/Playlist records, private Messenger isolation, private photo/audio access, weather and translation mocked integrations, and AI configuration. Tests do not substitute for a real Android or Windows packaging and user-acceptance run.

## Key directories

```text
apps/
  web/                       # Vainah UI; PWA manifests and icons
    assets/app.js            # Identity, launcher, Notes
    assets/suite-ui.js       # Other 10 app screens
  desktop/run.py             # Native pywebview window with local FastAPI server
  android/                   # Android Studio source wrapper
services/api/app/
  main.py                    # FastAPI application and PWA entry routes
  auth.py / security.py      # Vainah ID local MVP
  notes.py                   # Notes endpoints
  suite.py                   # Records, Messenger, private media
  integrations.py            # Weather, geocoding, translation, AI
  models.py / database.py    # Shared SQLite or PostgreSQL
services/api/tests/          # API integration tests
```

## GitHub repository

This project already lives in the [VainahEcosystem repository](https://github.com/isaevarbi822-hub/VainahEcosystem). Continue in this repository; do not create a replacement repository or upload a ZIP. Keep local databases, `.env` files, signing keys, and credentials out of Git. For current build instructions, see [MESSENGER-BUILD.md](MESSENGER-BUILD.md).

**IMPORTANT:** Do not publicly deploy prototype identity/messaging and do not invite real users until you have email verification, password recovery, abuse protection, moderation/blocking, encrypted backups, migrations, privacy review and security audit. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
