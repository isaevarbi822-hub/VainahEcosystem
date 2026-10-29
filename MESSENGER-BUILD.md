# Vainah Messenger 0.7.0 — Windows and Android builds

The source code ships with a GitHub Actions build pipeline. It creates two independent **debug** Android packages and two **unsigned** Windows EXE files.

1. Upload the contents of the complete 0.7.0 ZIP to your **VainahEcosystem** GitHub repository, preserving the folders. Do not upload `data/`, `.env`, test caches, databases or secrets.
2. In GitHub → Settings → Secrets and variables → Actions → **Variables**, set `VAINAH_BASE_URL` to the exact HTTPS base URL of the Vainah server on Render, without a path (only after you have a working backend).
3. In GitHub → Actions → `Build Vainah EXE and APK` → **Run workflow**. Wait for both jobs to complete successfully.
4. Download the artifacts `Vainah-Windows-v0.7.0` and `Vainah-Android-v0.7.0` from that run. Extract the ZIPs: `Vainah-Messenger.exe` and `Vainah-Ecosystem.exe` from Windows; `Vainah-Messenger-v0.7.0-debug.apk` and `Vainah-Ecosystem-v0.7.0-debug.apk` from Android.

**Warning:** No EXE/APK is contained in this source ZIP. Windows executable is unsigned and Android APK is a debug build. Windows EXE uses a local SQLite database by default: configure `%LOCALAPPDATA%/Vainah/Ecosystem/server-url.txt` with your HTTPS Render URL to use shared accounts; Android APK uses the `VAINAH_BASE_URL` build setting. Not yet suitable for public release.

Voice recording is experimental. Windows browser/WebView and Android have different microphone permission systems; verify on each device. Group chat is text-only, no E2EE, no calling and no push notifications.

## Realtime and calling (0.7.0)

Serve the main FastAPI app with **one** worker (the current `render.yaml` does this). Browser receives same-origin `wss://YOUR_RENDER_HOST/api/messenger/v2/live`; WebRTC signalling stays in the same connection. Do not use VAINAH_BASE_URL as a secret. `APP_ORIGIN=https://YOUR_RENDER_HOST` must match exactly. Media requires HTTPS/camera and microphone permissions. No TURN, no Web Push and no calls in the background. For production use audited authentication, monitoring, TURN and distributed pub/sub.
