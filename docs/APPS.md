# App targets and launch modes

**Current:** one FastAPI backend, one web UI with 11 modules. On Windows, pywebview opens it as a dedicated desktop window; on Android, a WebView package loads the same remotely served UI. Each of the 11 modules can also be opened at `/app/{name}` for a distinct PWA manifest and icon.

### What gets installed

| Target | Artifact | Requires |
|---|---|---|
| Windows developer app | `start-windows.bat` plus source | Python installed, deps downloaded |
| Windows build | `build-windows-exe.bat` creates `dist/Vainah-Ecosystem/` | Actual Windows machine, Python, PyInstaller, pywebview |
| Android | Android Studio project at `apps/android/` | SDK 36 + Gradle; running HTTPS API or adb reverse to local server |
| Browser/PWA | `/app/ai`, `/app/music`, etc. | Modern browser; HTTPS for installation |
| macOS / Linux | Same source, `python apps/desktop/run.py` | Python and desktop dependencies; not packaged here |
| iOS | HTTPS web/PWA preview only | No signed native iOS application in this release |

### Eleven Windows app launchers

`apps/desktop/launchers/Vainah-{AI,Messenger,Browser,Music,Weather,Maps,Notes,Translate,Study,Photos,Calendar}.bat` open the selected app screen in a pywebview window. The first window starts the shared local API; later windows reuse it. Keep the first window open while using others. These are development launchers requiring Python; **not** separately signed Windows EXEs.

### Limitations

- 11 app modules are **not** 11 independent Android APKs or Windows installers.
- Android is not an offline standalone server: a working Vainah API is mandatory.
- End-to-end encryption, push notifications, offline sync, separate browser engine, and native background services are not implemented.
- Do not use real personal secrets in the local prototype.


## Messenger 0.6.0

Отдельная оболочка для Windows/Android и PWA, диалоги, сообщения, квитанции прочтения, реакции, редактирование, удаление, блокировка, фото и аудиовложения. Без E2EE, push и звонков.
