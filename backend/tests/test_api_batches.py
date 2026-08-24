"""
Tests for Batch REST API endpoints using FastAPI TestClient.
"""

import io
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


class TestBatchAPI:
    def test_health_check(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_create_and_get_batch(self):
        create_resp = client.post("/api/batches")
        assert create_resp.status_code == 201
        batch_data = create_resp.json()
        assert "batch_id" in batch_data
        batch_id = batch_data["batch_id"]

        get_resp = client.get(f"/api/batches/{batch_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["batch_id"] == batch_id

    def test_upload_files_and_process_batch_flow(self):
        # 1. Create batch
        create_resp = client.post("/api/batches")
        batch_id = create_resp.json()["batch_id"]

        # 2. Upload file
        line = build_valid_record()
        file_content = (line + "\n").encode("utf-8")
        files = [
            ("files", ("test_file_01.txt", io.BytesIO(file_content), "text/plain"))
        ]
        upload_resp = client.post(f"/api/batches/{batch_id}/upload", files=files)
        assert upload_resp.status_code == 200
        uploaded_files = upload_resp.json()
        assert len(uploaded_files) == 1
        assert uploaded_files[0]["status"] == "READY"

        # 3. Check progress before process
        progress_resp = client.get(f"/api/batches/{batch_id}/progress")
        assert progress_resp.status_code == 200
        assert progress_resp.json()["total_files"] == 1

        # 4. Trigger process
        process_resp = client.post(f"/api/batches/{batch_id}/process")
        assert process_resp.status_code == 200

        # 5. Check progress after process (eager mode completes immediately)
        progress_resp2 = client.get(f"/api/batches/{batch_id}/progress")
        assert progress_resp2.status_code == 200
        data = progress_resp2.json()
        assert data["completed_files"] == 1
        assert data["valid_records"] == 1
        assert data["progress_percentage"] == 100.0

    def test_overview_stats_pipeline_stages(self):
        resp = client.get("/api/batches/overview/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert "total_records_parsed" in stats
        assert "awaiting_verification" in stats
        assert "committed_to_db" in stats
        assert "duplicates_skipped" in stats
        assert "failed_records" in stats

    def test_get_batch_parsed_records_and_masking(self):
        # 1. Create and process batch
        create_resp = client.post("/api/batches")
        batch_id = create_resp.json()["batch_id"]

        line = build_valid_record(
            aadhaar="123456789012",
            dest_bank_account="98765432101234",
            user_credit_ref="PARSED_REC_01"
        )
        files = [
            ("files", ("parsed_test.txt", io.BytesIO((line + "\n").encode("utf-8")), "text/plain"))
        ]
        client.post(f"/api/batches/{batch_id}/upload", files=files)
        client.post(f"/api/batches/{batch_id}/process")

        # 2. Query parsed records endpoint
        resp = client.get(f"/api/batches/{batch_id}/records?page=1&page_size=50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["records"]) >= 1

        rec = data["records"][0]
        # PII fields are returned unmasked by default (mask_pii=False)
        assert "123456789012" in rec["beneficiary_aadhaar_number"]
        assert "98765432101234" in rec["destination_bank_account_number"]
        # Must have 18th status column
        assert "status" in rec

    def test_logs_endpoint_filtering(self):
        # Trigger an action that logs
        create_resp = client.post("/api/batches")
        batch_id = create_resp.json()["batch_id"]

        resp = client.get(f"/api/logs?batch_id={batch_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_delete_single_record_endpoint(self):
        # 1. Create and upload batch with a record
        create_resp = client.post("/api/batches")
        batch_id = create_resp.json()["batch_id"]

        line = build_valid_record(
            user_credit_ref="DEL_TEST_001"
        )
        files = [
            ("files", ("del_test.txt", io.BytesIO((line + "\n").encode("utf-8")), "text/plain"))
        ]
        client.post(f"/api/batches/{batch_id}/upload", files=files)
        client.post(f"/api/batches/{batch_id}/process")

        # 2. Test deleting the record by reference
        del_resp = client.delete(f"/api/batches/records/1?ref=DEL_TEST_001&batch_id={batch_id}")
        assert del_resp.status_code == 200
        del_data = del_resp.json()
        assert del_data["success"] is True


