# Build EXE and APK — Vainah Ecosystem 0.4.0

The project is built on native runners through GitHub Actions because PyInstaller requires Windows for Windows EXEs and Android APKs require the Android SDK.

## One-time setup

1. Unzip `Vainah-Ecosystem-v0.4.0-BUILD-READY.zip`.
2. Open the GitHub repository `VainahEcosystem` and upload the **contents** of the `vainah-ecosystem` folder (not the ZIP file itself), keeping `.github/workflows/build-installers.yml` and all nested directories intact.
3. For an Android APK that logs into the same Neon/Render Vainah ID as the web app, open GitHub → Settings → Secrets and variables → Actions → Variables → New repository variable:
   - Name: `VAINAH_BASE_URL`
   - Value: `https://YOUR-VAINAH-RENDER-SERVICE.onrender.com` (without a slash at the end)
   - Do not set this to a link containing an API token or secret.
4. Open GitHub → Actions → `Build Vainah EXE and APK` → `Run workflow`. Wait for both green jobs.
5. Open the completed run and download the two **Artifacts**: `Vainah-Windows-EXE-v0.4.0` and `Vainah-Android-APK-v0.4.0`.
6. Unzip each GitHub artifact. The first contains `Vainah-Ecosystem.exe`; the second contains `Vainah-Android-v0.4.0-debug.apk`.

## Important limitations

- Without `VAINAH_BASE_URL`, the APK points to http://127.0.0.1:8000, usable only for local USB development with `adb reverse tcp:8000 tcp:8000` and a running local API.
- Windows EXE defaults to a LOCAL Vainah account/database. To use the SAME Vainah ID as Android, put one line containing the HTTPS Render server address into `%LOCALAPPDATA%\Vainah\Ecosystem\server-url.txt` before opening the EXE. Do not include a trailing slash, API token, or path.
- Windows needs Microsoft Edge WebView2 Runtime (typically installed on Windows 11).
- APK is a debug-signed Android WebView wrapper; it is not a Google Play-ready release package. Installing it can trigger Play Protect prompts. Never bypass a warning for an untrusted build: verify the build came from your own GitHub Actions.
- The backend remains a limited private beta. Do not invite real users or use sensitive accounts until email verification, abuse protection, database migration and security audit are completed.
- CI builds use remote downloads of Python libraries, Gradle and Android SDK. The build must finish successfully before an EXE or APK exists.

## Local build alternatives

On Windows 11: double-click `build-windows-exe.bat` after installing Python 3.12+. EXE appears at `dist\Vainah-Ecosystem.exe`.

On a computer with Android Studio: open `apps/android`, sync Gradle and choose **Build APK(s)**; output `apps/android/app/build/outputs/apk/debug/app-debug.apk`. The CI workflow does not need the Gradle wrapper file because it installs Gradle directly.
