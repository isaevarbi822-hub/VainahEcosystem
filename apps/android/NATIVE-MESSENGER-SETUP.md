# Vainah Messenger Android 0.9.0 — нативное приложение

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

Скачайте artifact `Vainah-Android-v0.9.0`, распакуйте ZIP и установите **`Vainah-Messenger-v0.9.0-debug.apk`**. Тестируйте на телефоне, используя реальный HTTPS API. Сайт открывать не требуется.

## Ограничения текущего MVP

- Реальные личные сообщения, просмотр групп, каналы, подписки, простые боты, Vainah ID, Google/email вход; сервер обязателен для синхронизации.
- В этом нативном Android выпуске нет готовых системных push-уведомлений, фонового WebSocket, голосовых/видеозвонков, загрузки медиа и сквозного шифрования. Веб-реализация некоторых из этих функций не означает, что они работают в нативной Android Activity.
- Не проверено на реальном телефоне до установки пользователем. Успешная CI-компиляция не заменяет устройство.
