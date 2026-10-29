# Build Windows EXE + Android APK — Vainah 0.7.0

See [MESSENGER-BUILD.md](MESSENGER-BUILD.md) for detailed steps.

- GitHub workflow: `.github/workflows/build-installers.yml`
- Windows artifacts: `Vainah-Windows-v0.7.0` (Ecosystem.exe and Messenger.exe)
- Android artifacts: `Vainah-Android-v0.7.0` (2 debug APKs, separate package IDs)
- Android Gradle plugin: 9.4.0; Gradle: 9.6.0; JDK 21 on GitHub Actions; compileSdk 36.
- Set `VAINAH_BASE_URL` only to your own **HTTPS** Render origin to allow real-device remote login.

These binaries must be produced and tested by the GitHub runners. No code signing, push infrastructure or public-production security assurance is provided.
