# Vainah Messenger Android 0.9.3 — нативное приложение

В Messenger на Android используется **NativeMessengerActivity**, настоящие Android Views и системный Google Credential Manager. Никаких WebView, экранов ввода адреса сайта или HTML-приложения. Отдельный старый `Vainah Ecosystem` APK пока остаётся WebView, потому что его изменение не входило в этот этап.

**Для удалённых переписок всё равно нужен Vainah API**: Python FastAPI на Render (или другом HTTPS-хосте), база Neon/PostgreSQL. Сервер обслуживает API, не интерфейс Android. APK без настроенного API не сможет обмениваться сообщениями между пользователями.

## 1. GitHub Variables (публичные)

GitHub → репозиторий VainahEcosystem → Settings → Secrets and variables → Actions → **Variables**:

- `VAINAH_BASE_URL`: точный HTTPS origin сервера Vainah API, например `https://<ВАШ-СЕРВИС>.onrender.com`. Не добавлять `/app/messenger`, завершающий слэш или адрес VainahNews/VainahVPN.
- `VAINAH_GOOGLE_WEB_CLIENT_ID`: **Web application OAuth Client ID** из Google Cloud. Это **публичный Client ID**, не Client Secret. Он должен совпадать с `GOOGLE_CLIENT_ID` на Render.

## 2. Постоянная подпись APK (GitHub Secrets)

Google Android OAuth требует тип `Android`, `package name` и SHA-1 сертификата подписи APK. Временная debug-подпись GitHub Actions меняется от сборки к сборке. Используйте свою постоянную подпись и храните её отдельно от репозитория.

Создайте локальный ключ на Windows с JDK, например в PowerShell:

```powershell
keytool -genkeypair -v -keystore vainah-signing.jks -storetype PKCS12 -alias vainah -keyalg RSA -keysize 3072 -validity 10000
keytool -list -v -keystore vainah-signing.jks -alias vainah
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes((Resolve-Path .\vainah-signing.jks)))
```

- **Не загружайте** `vainah-signing.jks` в публичный репозиторий и никому не сообщайте пароль.
- Сохраните защищённую резервную копию файла подписи.
- В Google Cloud → OAuth Clients → Create Client → **Android** задайте package **`no.vainah.messenger`** и SHA-1 из команды `keytool -list`.
- Если Google OAuth находится в Testing, укажите аккаунт в Audience → Test users.
- При использовании тестового APK с другой подписью Google может отказать во входе. Для следующей стабильной сборки используйте тот же JKS.

GitHub → Settings → Secrets and variables → Actions → **Secrets**:

| Секрет | Значение |
|---|---|
| `VAINAH_ANDROID_SIGNING_KEYSTORE_BASE64` | Результат последней PowerShell-команды, base64 всего JKS файла |
| `VAINAH_ANDROID_SIGNING_STORE_PASSWORD` | Пароль хранилища JKS |
| `VAINAH_ANDROID_SIGNING_KEY_ALIAS` | `vainah` или выбранный alias |
| `VAINAH_ANDROID_SIGNING_KEY_PASSWORD` | Пароль ключа внутри JKS |

Не добавляйте сюда пароль своего Google-аккаунта. `DATABASE_URL`, ключи Neon и секреты серверной части хранятся только в Render, **не в APK**.

## 3. Server (Render)

В Render Web Service:

- `GOOGLE_CLIENT_ID`: тот же Web OAuth Client ID, что указан в GitHub Variable.
- `DATABASE_URL`: серверная строка подключения, **только на сервере**.
- `APP_ORIGIN`: точный HTTPS origin.
- `VAINAH_SIGNUP_MODE=open` — только если нужна регистрация по email без приглашения. До публичного запуска настройте подтверждение email, спам-контроль и модерацию.

Бэкенд продолжает проверять Google ID-токены, создавать защищённые сессии и проверять права на каналы и чаты. Наличие Google-аккаунта с тем же email **не привязывает** его автоматически к старому Vainah ID: сначала войдите по email, затем выберите «Подключить вход Google» в настройках.

## 4. Проверка сборки

GitHub → Actions → **Build Vainah EXE and APK** → Run workflow. Задание Android сначала компилирует нативный вариант, затем не публикует Android APK, если отсутствуют обязательные публичные переменные или постоянная подпись. Это предохраняет от скачивания APK с нерабочей авторизацией.

Скачайте artifact `Vainah-Android-v0.9.3`, распакуйте ZIP и установите **`Vainah-Messenger-v0.9.3-debug.apk`**. Тестируйте на телефоне, используя реальный HTTPS API. Сайт открывать не требуется.

## Ограничения текущего MVP

- Реальные личные сообщения, создание групп (приглашение по email), просмотр групп с непрочитанными, каналы, подписки, простые боты, Vainah ID, Google/email вход; сервер обязателен для синхронизации.
- В этом нативном Android выпуске нет готовых системных push-уведомлений, фонового WebSocket, голосовых/видеозвонков, загрузки медиа и сквозного шифрования. Веб-реализация некоторых из этих функций не означает, что они работают в нативной Android Activity.
- Не проверено на реальном телефоне до установки пользователем. Успешная CI-компиляция не заменяет устройство.

## 0.9.3 — публичные @username

- Пользователь назначает уникальное имя в Android → Настройки. Имя 5–32 символа: латиница, цифры и `_`, начинается с буквы.
- В поиске чатов можно искать по `@username`, при этом email не раскрывается. Имена не создаются автоматически и доступны после добровольного назначения.
- Группы создаются с приглашением участников по `@username`; владелец может приглашать новых участников в существующую группу.
- Владелец канала может отправить приглашение по `@username`. Адресат принимает или отклоняет его в разделе Каналы, автоматической подписки нет.
- База данных дополняется новыми таблицами `messenger_user_handles` и `messenger_channel_invitations` через существующий `Base.metadata.create_all`. Для полноценного production-развёртывания в дальнейшем нужна Alembic миграция.

## Native UI & Apple ID 0.9.3

Native dark interface: Chats, Contacts, Settings and Profile. Filter tabs show personal chats, groups, channels and bots. Search by voluntary public @username; edit profile display name.

Apple ID is an optional, server-verified OAuth login using the system browser, not WebView. Apple requires a developer team with a Sign in with Apple App ID, associated Services ID, registered HTTPS domain/return URL, Team ID, Key ID and private .p8 key.

Set on the Render API service only (never in the public GitHub repo or APK):
- APPLE_SERVICE_ID: Services ID from Apple Developer
- APPLE_TEAM_ID: Apple Team ID
- APPLE_KEY_ID: Sign in with Apple Key ID
- APPLE_PRIVATE_KEY_P8: full private key PEM text (.p8)
- APPLE_REDIRECT_URI: https://vainahecosystem.onrender.com/api/auth/apple/callback (or your exact registered HTTPS callback)

APP_ORIGIN must match the HTTPS server origin. The callback is an Apple form_post, and the browser returns to vainah-messenger://auth/apple via a one-use, app-bound proof. Until Apple Developer setup is complete, the login UI explains that Apple sign-in is unavailable. Existing Google/email accounts with the same email will not be silently linked.

Setup: https://developer.apple.com/help/account/capabilities/configure-sign-in-with-apple-for-the-web

The Android app must be tested on a real device; successful compilation alone does not validate Apple credentials.


## 0.9.4 — Постоянный Vainah ID

- У каждого пользователя есть уникальный 10-значный **Vainah ID**, например 6182903745 (просто пример).
- Он не меняется при изменении публичного @username, смене устройства или повторном входе.
- В Android → Профиль отображается Vainah ID и кнопка «Копировать».
- В Android → Контакты можно найти человека по точному числовому ID. Частичный поиск ID не поддерживается; блокировки соблюдаются.
- ID выдаётся сервером и хранится в таблице \`vainah_public_ids\` с ограничением уникальности. Существующие пользователи получают номер при первом авторизованном обращении к API после обновления.
- Внутренний UUID продолжает использоваться в API как технический ключ. Vainah ID — отдельный публичный номер, это не Telegram ID и не номер телефона.
- Для реальной работы необходимо обновить сервер Python на Render одновременно с Android.


## 0.9.5 — исправления стабильности и управление чатами

- Сервер возвращает @username контакта в списке существующих личных переписок и в информации о контакте, а не только в результатах поиска.
- Нативный чат не перерисовывает все сообщения, если сервер вернул тот же список; повторные запросы одной и той же переписки не накапливаются.
- Следующий набранный текст не стирается при успешной отправке предыдущего сообщения.
- Реальное меню ⋮: закрепление, отключение звука, архивирование и блокировка личного чата; показ участников, приглашение, выход/удаление группы.
- Если сессия истекла, клиент возвращает на экран входа вместо бесконечных ошибок загрузки.
- Back возвращает в исходный раздел; поиск уже существующих чатов понимает @username.
- Клиент принимает и хранит только cookie \`vainah_session\`, а не произвольные cookies.
- Системные push, видеозвонки, сквозное шифрование, фото профиля и offline-хранилище переписок пока не реализованы.
- Проверка в CI не заменяет проверку Google/Apple входа и сообщений на телефоне. Обновлённый Python API нужно развернуть на Render.


## 0.9.6 — real-time, серверная галочка и защита хранения

### Мгновенное обновление
- Нативный Android Messenger соединяется по **WSS** с существующим \`/api/messenger/v2/live\` с cookie своей сессии, не добавляя токены в URL.
- Сообщения и события групп обновляют открытые чаты сразу, пока приложение активно. Резервное REST-обновление остаётся. При временном обрыве соединение переподключается с паузами.
- В личных чатах есть одноразовый индикатор **«печатает…»**, передаётся только сигнал, не набираемый текст.
- Для собственных отправленных сообщений показывается ✓ или ✓✓ в зависимости от подтверждённого сервером прочтения.
- Это **не** Android push: если приложение закрыто, уведомления вне приложения пока не работают.

### Подтверждение аккаунта
- Галочка выдаётся/снимается **только администратором** из \`VAINAH_VERIFICATION_ADMIN_IDS\` на сервере. Владелец Vainah ID сам себе её поставить не может.
- Галочка показывается в профиле, результатах поиска по никнейму или точному ID и личных чатах. Администратор может указать UUID, Vainah ID или \`@username\`.

### Шифрование сообщений в базе (AES-256-GCM)
- Новый \`EncryptedMessageText\` хранит новые тексты **личных и групповых сообщений** в зашифрованном виде, когда серверу передан корректный \`VAINAH_MESSAGE_ENCRYPTION_KEY\`. Работает и с legacy API через общие модели SQLAlchemy.
- Generate a 32-byte key once and copy the output privately into **Render → Environment**:

\`\`\`powershell
python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
\`\`\`

- Name on Render: \`VAINAH_MESSAGE_ENCRYPTION_KEY\`; Value: generated private Base64 string.
- NEVER put the key in GitHub, Android APK, screenshots or this chat. Store a secure offline backup. Key loss makes encrypted messages unreadable; changing it without a planned migration breaks decryption.
- Existing older plaintext records remain readable and **are not retroactively encrypted automatically**. Images/files and other app data are not covered by this message-body encryption.
- The Vainah server holds the key and decrypts messages for clients. **Это не сквозное шифрование (E2EE).** Нельзя маркировать обычные чаты как «E2EE» до отдельного клиентского протокола с ключами на устройствах, проверкой идентичности и аудитом.
- If Render has not been updated or the key is missing, plaintext storage is still possible. This release alone does not prove live data is encrypted.

## 0.9.8 — действия с личными сообщениями

- Удерживайте сообщение, чтобы открыть контекстное меню. В личном чате доступны **Ответить, Реакция, Копировать**; автору также **Изменить** (в первые 15 минут) и **Удалить**.
- Поддерживаются реакции ❤️ 👍 😂 😮 😢 🔥. Повторный выбор своей реакции снимает её на сервере.
- Ответ показывает короткую цитату в переписке; баннер над строкой ввода можно отменить. Черновик, введённый после отправки, не стирается.
- Кнопка поиска (⌕) в заголовке личной переписки ищет в последних 1000 сообщениях; текст поиска на Android не переносится в сторонние сервисы.
- Редактирование и удаление чужих сообщений запрещено сервером; удаление требует подтверждения.
- Имена файлов вложений выводятся вместо пустых пузырей. Полноценный просмотр/отправка медиа на Android ещё в разработке.
- В группах в текущей версии сервер поддерживает копирование, но не редактирование/реакции/ответы; приложение не обещает несуществующие действия.
- Шифрование серверного хранилища через AES-GCM и защита HTTPS сохранены, однако E2EE пока не реализовано.

## 0.10.0 — Voice, video notes, photos and files (Android)

Grounded in Telegram's public feature documentation, but Vainah implements its own native Android UI.

- Tap **＋** to open Android document picker for pictures, videos, audio and files (choose up to 5). Accepted formats are JPEG, PNG, GIF, WebP, MP3, OGG, WAV, M4A/AAC, MP4, WebM, PDF, ZIP. The backend verifies format signatures; unsupported attachments are rejected.
- Tap **🎤** to start a native microphone recording, tap **■** to stop and send. Long-press to cancel the voice message. Permission is requested at runtime. The file is saved temporarily in app-private cache.
- Tap **◉** to launch Android's camera app for a short **video note** (maximum requested duration 15 seconds); after recording it is sent as a video note and plays in a round-cropped Android viewer. Some camera apps may not honor duration/quality extras, or may return unsupported files; test on actual device.
- Tap an incoming attachment to download with the current account's HTTP session and view/play in a private preview. Photos, audio/voice, videos and round video notes have viewers. Documents are opened with a system app using a temporary FileProvider grant.
- Direct AND group messages have separate authenticated upload/download endpoints with membership validation. A non-member cannot download private group attachments. Voice and notes are shared via the same server as text.
- Server caps: images 8 MB, audio 12 MB, video 20 MB, PDF/ZIP 12 MB; file bytes are currently stored server-side in the database. For a production service, migrate these binary blobs to a private object store with limits, scans and retention rules.
- The verified blue badge still comes from the server, and verified group senders are marked. Existing Google sign-in, @username, Vainah ID, live chat and optional AES-GCM encrypted **message body** storage are preserved.
- **Limitations**: no full photo/video editing, auto-compression, photo albums, stories, calls or background push yet. Camera output on OEM devices needs manual testing. Attachments currently are NOT encrypted at rest by the text-only `VAINAH_MESSAGE_ENCRYPTION_KEY`; E2EE is NOT implemented. Never advertise them as fully private E2EE media.
- Backend deployment on Render must use new server commit before the mobile client can send large video/files or group attachments. Reactivation of App Store/Apple Sign In also requires valid Apple Developer setup.
