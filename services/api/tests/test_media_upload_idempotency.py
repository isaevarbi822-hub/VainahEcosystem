"""Regression tests for retry-safe direct media uploads."""
import io
from services.api.app.main import create_app
from services.api.tests.test_messenger_050 import new_user


def test_media_upload_idempotency(tmp_path):
    app = create_app(f"sqlite:///{tmp_path/'media_retries.db'}")
    try:
        alice, aid, ha = new_user(app, "upload_a@example.net")
        bob, bid, hb = new_user(app, "upload_b@example.net")
        key = "d7342c9d-c931-49aa-a7c5-d21374cfe022"
        headers = {**ha, "X-Upload-Id": key}
        payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
        def upload(data):
            return alice.post(
                "/api/messenger/v2/send-file",
                data={"contact_id": bid},
                files={"file": ("document.pdf", io.BytesIO(data), "application/pdf")},
                headers=headers,
            )
        first = upload(payload)
        assert first.status_code == 201, first.text
        repeated = upload(payload)
        assert repeated.status_code == 201, repeated.text
        assert repeated.json()["id"] == first.json()["id"]
        conflict = upload(payload+b"altered")
        assert conflict.status_code == 409, conflict.text
        thread = bob.get(f"/api/messenger/v2/thread/{aid}")
        assert len(thread.json()["items"]) == 1
    finally:
        app.state.engine.dispose()
