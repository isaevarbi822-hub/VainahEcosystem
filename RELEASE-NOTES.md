# Vainah Ecosystem 0.7.0 — Messenger Live & Call Preview

## Delivered

- Authenticated same-origin WebSocket `/api/messenger/v2/live`: real-time alerts for new/edited/deleted messages, receipts, group activity and updated chat lists. Uses current Vainah ID session cookie. Missing/foreign Origin and unauthenticated connections are rejected. Session validity is rechecked at least every 35 seconds.
- Foreground live indicator with automatic reconnect; HTTP polling remains as fallback when socket is offline.
- Optional browser notifications: enabled only after the user clicks the permission button, and only while Messenger is open. **Not background push**.
- Experimental private one-to-one voice/video calls using WebRTC, with WebSocket signalling, incoming call dialog, accept, decline and hang-up. SDP and ICE are forwarded only between authenticated parties, never stored in the database. Blocked users cannot initiate calls. Microphone and camera permissions are explicitly requested.
- Android WebView requests the camera/microphone only for the configured trusted origin and exposes VIDEO_CAPTURE for video calls.
- One-to-one signalling tested with 3 independent authenticated users (including forbidden third-party call actions); existing app suite preserved.

## Limits / prerequisites

- **Not a WhatsApp-ready production release.** This is a personal/private preview, not a secure production messaging system.
- Messenger messages are readable server-side: **no end-to-end message encryption**.
- WebSocket broker and active calls live only in the Python process. Configure ONE Uvicorn worker; restarting the service drops sockets/calls. Multiple instances require Redis Pub/Sub and distributed call coordination first.
- WebRTC has public STUN only; **TURN is not configured**. On mobile/corporate NAT, calls may fail or have one-way media. Configure a TURN service with short-lived credentials before public release; do not commit permanent TURN credentials to browser JavaScript.
- Caller and receiver must both have the Messenger screen open. Android app does NOT implement FCM notifications or accept calls in the background; no background Android camera/microphone capture.
- Browser alerts are opt-in and available only with compatible browser APIs and HTTPS (or localhost). No Web Push service.
- The call media is peer-to-peer and uses WebRTC transport encryption; this is **not** evidence that messages are E2E encrypted, nor is identity verified against external authorities.
- Windows EXE and Android APK workflows are updated to v0.7.0, but require cloud builds and device validation. No signed release binaries have been created in the authoring environment.
- Upgrade in a **private test deployment only** with a Neon backup. Server schema is unchanged from 0.6.

## Validation

- Python API tests including WebSocket authentication, direct message notifications and call authorization: 45 passed.
- `python -m compileall -q services`: passed.
- Node.js `node --check` on app.js, suite-ui.js, messenger-live.js: passed.
- Chromium browser automation could not run in this environment (administrator-blocked navigation). Full UI/call execution and Android/Windows compilation are not verified.

# Vainah Messenger 0.6.0 — Community Preview

This is a **private prototype**, not a production messenger. Version 0.6.0 preserves all 11 Vainah Ecosystem app modules and the existing direct-chat data model.

## New capabilities

- **Groups:** create groups, add members via exact Vainah ID email, group messaging, member list, admin-only invitations, members can leave, owners can delete a group. Max 25 members per group; group messages currently support text only.
- **Direct chat preferences:** independent pin/archive/mute flags for each user, server-stored.
- **Direct replies:** reply to a specific message with a compact quoted context; cannot reference a third-party conversation or a deleted message.
- **Direct message search:** find text inside your own two-person chat with server-side access enforcement; deleted messages are excluded.
- **Voice message preview:** record from supported browsers using MediaRecorder (WebM/Ogg, max 5 MB), send to an existing direct chat. Android WebView requests microphone permission only for the configured Vainah origin. Requires HTTPS (or localhost), permission, microphone support and testing on device.
- **Navigation:** messenger quick access from desktop and mobile navigation, filters All/Unread/Groups/Archive, chat settings, clearer group participants and a reply banner.
- **Independent app installation:** Windows PyInstaller workflow builds Vainah Messenger.exe and Vainah Ecosystem.exe. Android Gradle workflow creates separate debug APKs with distinct application IDs and icons. These builds require a working GitHub Actions runner and have **not** been compiled in this authoring environment.

## Compatibility and storage

The existing user, session, note and `direct_messages` tables are unchanged. New tables (`messenger_groups`, `messenger_group_members`, `messenger_group_messages`, `messenger_chat_preferences`, `message_replies`) are created on app startup in the private preview. Make a database backup before deployment. A future public release needs Alembic migrations, HTTPS, monitoring, backups, independent penetration testing, push infrastructure and proper identity verification.

The backend currently polls every four seconds instead of maintaining a websocket connection. A group member may see older group history upon joining. There are **no voice/video calls, stories, group attachments, E2EE, push notifications, or production-grade group moderation**. Never claim that messages are end-to-end encrypted.

## Quality checks

- Python FastAPI regression suite: **42 / 42 passed** using isolated temporary SQLite databases.
- JavaScript parsed successfully with `node --check`.
- Browser UI end-to-end testing was **blocked by environment policy**. Android APK and Windows EXE have **not** been built or installed in this environment. Check GitHub Actions and test on physical devices before distribution.
