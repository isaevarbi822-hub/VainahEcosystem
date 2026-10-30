# Build Vainah Messenger — current workflow

Build from the existing [VainahEcosystem repository](https://github.com/isaevarbi822-hub/VainahEcosystem). Do not upload a ZIP or create a replacement repository.

## Configure Android builds

In **GitHub → Settings → Secrets and variables → Actions**, configure:

- Variables: `VAINAH_BASE_URL` (the HTTPS origin of the deployed API) and `VAINAH_GOOGLE_WEB_CLIENT_ID`.
- Secrets: `VAINAH_ANDROID_SIGNING_KEYSTORE_BASE64`, `VAINAH_ANDROID_SIGNING_STORE_PASSWORD`, `VAINAH_ANDROID_SIGNING_KEY_ALIAS`, and `VAINAH_ANDROID_SIGNING_KEY_PASSWORD`.

See [native Android setup](apps/android/NATIVE-MESSENGER-SETUP.md) for generating and protecting a persistent signing key. Keep the keystore and all secret values out of the repository and chat.

## Start a build

1. Open **Actions → Build Vainah EXE and APK**.
2. Select **Run workflow**, or push a change to one of the paths monitored by the workflow.
3. Wait for all required jobs to finish successfully before distributing any artifact.

## Artifact names in the current workflow

- Windows: `Vainah-Windows-v0.9.0`, containing `Vainah-Messenger.exe` and `Vainah-Ecosystem.exe`. The Windows artifact label is still set to `v0.9.0` in the workflow and is not a source-version guarantee.
- Android: `Vainah-Android-v0.10.1`, containing `Vainah-Messenger-v0.10.1-debug.apk` and `Vainah-Ecosystem-v0.10.1-debug.apk`.

The Messenger Android package is native; the separate Ecosystem APK remains a WebView app. Android publication is blocked when the required configuration is absent, even if Java compilation itself succeeds. After a failure, download `Vainah-Android-build-diagnostics` and inspect `android-ci-logs/messenger.log` or `ecosystem.log`.

The server/API must be updated and reachable at the configured HTTPS origin. CI success does not establish real-device login, network, camera, audio, or video behavior. Both Android artifacts are debug builds and the Windows EXEs are unsigned; this workflow does not create a production-signed release.
