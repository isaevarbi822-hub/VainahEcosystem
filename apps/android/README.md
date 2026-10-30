# Vainah Android — два приложения, версия 0.9.0

## Vainah Messenger (новая нативная версия)

Вариант `-PVAINAH_MESSENGER=true` запускает `NativeMessengerActivity`. Это **Android-приложение с собственными экранами**: Google/email вход, чаты, сообщения, каналы, боты, настройки. Оно не загружает сайт и не предлагает вводить URL пользователю. Переписка синхронизируется с удалённым Vainah API по HTTPS.

Для реальной установки нужны GitHub Variables (`VAINAH_BASE_URL`, `VAINAH_GOOGLE_WEB_CLIENT_ID`) и GitHub Secrets для постоянного Android signing certificate. Подробности: [NATIVE-MESSENGER-SETUP.md](NATIVE-MESSENGER-SETUP.md). Компиляция Android без настроенных Variables возможна для CI, но публикация непригодного APK заблокирована.

## Vainah Ecosystem (старый отдельный APK)

Отдельный APK `no.vainah.ecosystem` пока остаётся WebView-оболочкой для старых модулей. Это **не** нативный Vainah Messenger. Не путайте два APK.

## Базовая команда разработчика

```bash
gradle -p apps/android :app:assembleDebug -PVAINAH_MESSENGER=true -PVAINAH_BASE_URL=https://YOUR-API.onrender.com -PVAINAH_GOOGLE_WEB_CLIENT_ID=YOUR-WEB-OAUTH-CLIENT-ID
```

Без постоянного сертификата подписи Google OAuth может отказать на следующем APK. Для полноценных проверок используйте конфигурацию GitHub Actions и свой JKS. Никогда не добавляйте JKS, пароли, ключи базы данных или секреты Google в GitHub файлы или код Android.

У Android Messenger пока нет готовых системных push-уведомлений, фоновых звонков и сквозного шифрования. Не публикуйте тестовый APK как полностью защищённый публичный мессенджер.
