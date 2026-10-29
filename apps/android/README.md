# Vainah Android Studio — source preview 0.6.0

This is a native Android **WebView wrapper** around the eleven-module UI. It uses the same API as Windows and the web app. It is **not a pre-built APK** and **does not include an offline Python server**.

## Build a debug APK

1. Install Android Studio, Android SDK API 36 and JDK 17+.
2. Open `apps/android` in Android Studio and sync Gradle.
3. This source package does not ship `gradle-wrapper.jar`. When Gradle wrapper generation is needed, use an installed Gradle version compatible with Android Gradle Plugin 9 (consult current Android Studio compatibility) and run `gradle wrapper`, or use Android Studio's wrapper generation.
4. Run **Build → Build Bundle(s)/APK(s) → Build APK(s)**.
5. Output is typically `apps/android/app/build/outputs/apk/debug/app-debug.apk`.

## Connect over USB to Windows

Start `start-windows.bat` on Windows (or run the Python API on 127.0.0.1:8000), enable Android USB debugging, connect the phone, then run:

```powershell
adb reverse tcp:8000 tcp:8000
```

Open the debug Android app. It will connect to Windows via the USB bridge. Account and Notes/media data are stored on the PC, **not** inside the Android APK. Photos/music can be selected using the native Android file picker. For real remote access, first deploy an authenticated HTTPS API and set `VAINAH_BASE_URL` in `gradle.properties` to that exact HTTPS origin before recompiling. Never use HTTP except explicit localhost USB development.

## Security/limits

- TLS certificate errors are rejected.
- External top-level HTTPS links are passed to the system browser, not loaded as part of the trusted Vainah origin.
- JavaScript is enabled only for the first-party app UI; Android file access is disabled except through the system file chooser.
- Messenger isn't end-to-end encrypted; no calls or push notifications. Direct chats include blocking, voice uploads and browser recording (where microphone permission works). Groups are text-only.
- This preview is not ready for general public distribution or hosting real user data.

## Messenger and Ecosystem variants

The same Android project supports two independent debug packages:

```bash
gradle -p apps/android :app:assembleDebug -PVAINAH_BASE_URL=https://YOUR-RENDER-SERVICE.onrender.com
gradle -p apps/android :app:assembleDebug -PVAINAH_MESSENGER=true -PVAINAH_BASE_URL=https://YOUR-RENDER-SERVICE.onrender.com --rerun-tasks
```

Set the real backend URL; do not use the placeholder above. Messenger launches `/app/messenger`, uses `no.vainah.messenger` and requests microphone permission only for authorized Vainah voice recording. Ecosystem opens `/` and uses `no.vainah.ecosystem`. A single output `app-debug.apk` is overwritten between builds; GitHub Actions saves each under a separate filename. Both require the Python backend.
