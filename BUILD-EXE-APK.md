# Build Windows EXE and Android APK

Use the existing `VainahEcosystem` repository. Do not upload a project ZIP or create a second repository.

## Run the build

1. Open **Actions → Build Vainah EXE and APK** in GitHub.
2. Choose **Run workflow** for a manual build. Pushes to the configured app, service, requirements, and workflow paths also trigger it.
3. Wait for the API tests, Windows EXE, and Android APK jobs to finish. Download artifacts only from a completed successful run.

## Current artifacts and toolchain

- Windows artifact: `Vainah-Windows-v0.9.0`; contains `Vainah-Ecosystem.exe` and `Vainah-Messenger.exe`. The workflow currently retains the older `v0.9.0` artifact label for Windows; treat it as a workflow name, not a claim about the latest Messenger feature version.
- Android artifact: `Vainah-Android-v0.10.1`; contains `Vainah-Ecosystem-v0.10.1-debug.apk` and `Vainah-Messenger-v0.10.1-debug.apk`.
- Windows runner: Python 3.12 and PyInstaller. Android runner: JDK 17, Gradle 9.6.0, Android SDK/build tools 36.
- Both Android packages are debug APKs. The Windows EXEs are unsigned; these artifacts are not signed public releases.

## Required Android configuration

Set these in **GitHub → Settings → Secrets and variables → Actions**:

- Variables: `VAINAH_BASE_URL` (your exact HTTPS API origin) and `VAINAH_GOOGLE_WEB_CLIENT_ID`.
- Secrets: the four persistent Android signing values documented in [NATIVE-MESSENGER-SETUP.md](apps/android/NATIVE-MESSENGER-SETUP.md).

The Android workflow intentionally withholds the Messenger APK artifact unless the required URL, Google client ID, and signing secrets are configured. If the build fails, download `Vainah-Android-build-diagnostics` from that run and inspect `android-ci-logs/ecosystem.log` or `messenger.log`.

A successful CI run confirms that the configured build jobs completed; it does not prove sign-in, device networking, media, camera, or playback works on every phone. Test with a real device and the API deployment that will serve the app. Never commit signing files, secret values, database URLs, or server keys.
