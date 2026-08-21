"""
Integration tests for Human Verification Checkpoint, Previews, Downloads, and SQL Import API.
"""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.workers.celery_app import celery_app
from tests.conftest import build_valid_record


@pytest.fixture(autouse=True)
def enable_eager_celery():
    celery_app.conf.task_always_eager = True
    yield
    celery_app.conf.task_always_eager = False


client = TestClient(app)


class TestVerificationAndImportFlow:
    def test_end_to_end_verification_and_import_api(self):
        # 1. Create Batch
        create_resp = client.post("/api/batches")
        assert create_resp.status_code == 201
        batch_id = create_resp.json()["batch_id"]

        # 2. Upload file with unique transaction
        unique_ref = f"V_{uuid.uuid4().hex[:11]}"
        line = build_valid_record(user_credit_ref=unique_ref)
        file_content = (line + "\n").encode("utf-8")
        files = [
            ("files", ("verify_test.txt", io.BytesIO(file_content), "text/plain"))
        ]
        upload_resp = client.post(f"/api/batches/{batch_id}/upload", files=files)
        assert upload_resp.status_code == 200

        # 3. Process Batch
        process_resp = client.post(f"/api/batches/{batch_id}/process")
        assert process_resp.status_code == 200

        # 4. Preview Clean Records
        preview_resp = client.get(f"/api/batches/{batch_id}/preview/clean")
        assert preview_resp.status_code == 200
        preview_data = preview_resp.json()
        assert len(preview_data) >= 1
        assert preview_data[0]["user_credit_reference"].strip() == unique_ref

        # 5. Get Summary Text
        summary_resp = client.get(f"/api/batches/{batch_id}/summary")
        assert summary_resp.status_code == 200
        assert "APBS BATCH PROCESSING SUMMARY" in summary_resp.text

        # 6. Verify Batch (Human Checkpoint)
        verify_resp = client.post(f"/api/batches/{batch_id}/verify")
        assert verify_resp.status_code == 200
        assert verify_resp.json()["status"] == "VERIFIED"

        # 7. Download Outputs and Zip
        dl_resp = client.get(f"/api/batches/{batch_id}/download/output/verify_test_output.txt")
        assert dl_resp.status_code == 200

        zip_resp = client.get(f"/api/batches/{batch_id}/download/all")
        assert zip_resp.status_code == 200
        assert zip_resp.headers["content-type"] == "application/zip"

        # 8. Commit to SQL
        import_resp = client.post(f"/api/batches/{batch_id}/import")
        assert import_resp.status_code == 200
        import_data = import_resp.json()
        assert import_data["status"] == "IMPORTED"
        assert import_data["total_imported"] >= 1
