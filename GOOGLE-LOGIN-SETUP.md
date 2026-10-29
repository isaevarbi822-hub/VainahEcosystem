# Vainah ID — вход через Google и email

## Способы входа

- Email и пароль Vainah ID продолжают работать без Google Cloud.
- Google Identity Services работает на HTTPS-сайте Vainah в Chrome или Edge после настройки `GOOGLE_CLIENT_ID`.

## Настройка Google Cloud + Render

1. В Google Cloud Console откройте **APIs & Services → Credentials → Create Credentials → OAuth client ID**. Тип: **Web application**. При необходимости сначала настройте OAuth consent screen.
2. В **Authorized JavaScript origins** укажите точный HTTPS-адрес Render-сервиса, например `https://your-vainah.onrender.com` (без пути).
3. В Render в **Web Service → Environment** добавьте `GOOGLE_CLIENT_ID` со значением публичного OAuth Client ID (оканчивается на `.apps.googleusercontent.com`). Это **не** Google Client Secret.
4. Проверьте `APP_ORIGIN` — точный HTTPS origin Render. Перезапустите сервис.
5. При закрытой регистрации `VAINAH_SIGNUP_CODE` пользователю потребуется код приглашения для первого входа через Google.

## Старые аккаунты

Привязка Google по совпадающему email без подтверждения запрещена. Войдите по email и паролю, откройте **Настройки Vainah ID → Вход через Google** и привяжите Google с таким же email. После этого доступны оба способа.

## Встроенные Windows/Android приложения

Google не поддерживает OAuth через встроенные WebView (включая Android WebView и pywebview). Нельзя обходить это ограничение. Пока Google-вход поддерживается **на HTTPS-сайте в обычном браузере**. Нативным клиентам нужен отдельный OS-безопасный поток авторизации (Android Credential Manager / desktop system browser), который ещё не реализован. Email/пароль продолжает работать в приложении.

## Проверка

`python -m pytest -q services/api/tests` проверяет серверную авторизацию. Реальный Google login требует авторизованного origin и проверки в Chrome/Edge.
