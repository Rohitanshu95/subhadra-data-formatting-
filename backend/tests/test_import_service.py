"""
Tests for Bulk Idempotent Importer Service.
"""

import io
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.db_models import DBDuplicateLog, DBTransaction
from app.services.batch_manager import BatchManager
from app.services.import_service import ImportService
from tests.conftest import build_valid_record


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    yield db
    db.close()


class TestImportService:
    def test_import_clean_batch(self, memory_db):
        manager = BatchManager()
        batch = manager.create_batch()

        # Add 3 valid records in a file
        line1 = build_valid_record(user_credit_ref="IMPORT_001")
        line2 = build_valid_record(user_credit_ref="IMPORT_002")
        line3 = build_valid_record(user_credit_ref="IMPORT_003")
        content = (line1 + "\n" + line2 + "\n" + line3 + "\n").encode("utf-8")

        manager.add_file(batch.batch_id, "clean_import.txt", io.BytesIO(content))
        manager.process_batch(batch.batch_id)

        # Import into SQL
        importer = ImportService(chunk_size=2)
        result = importer.import_batch(batch.batch_id, memory_db)

        assert result.total_processed == 3
        assert result.total_imported == 3
        assert result.total_duplicates == 0

        # Check records in DB
        tx_count = memory_db.query(DBTransaction).count()
        assert tx_count == 3

    def test_reimporting_same_batch_is_idempotent(self, memory_db):
        manager = BatchManager()
        batch = manager.create_batch()

        line = build_valid_record(user_credit_ref="IDEMPOTENT_1")
        content = (line + "\n").encode("utf-8")
        manager.add_file(batch.batch_id, "idem.txt", io.BytesIO(content))
        manager.process_batch(batch.batch_id)

        importer = ImportService()
        # First import
        result1 = importer.import_batch(batch.batch_id, memory_db)
        assert result1.total_imported == 1
        assert result1.total_duplicates == 0

        # Second import (identical batch re-imported)
        result2 = importer.import_batch(batch.batch_id, memory_db)
        assert result2.total_imported == 0
        assert result2.total_duplicates == 1

        # Total in DB should still be 1, duplicates_log should have 1 entry
        assert memory_db.query(DBTransaction).count() == 1
        assert memory_db.query(DBDuplicateLog).count() == 1

    def test_import_cleans_up_dummy_input_storage(self, memory_db):
        import os
        from app.services.storage import get_batch_paths

        manager = BatchManager()
        batch = manager.create_batch()

        line = build_valid_record(user_credit_ref="CLEANUP_01")
        content = (line + "\n").encode("utf-8")
        manager.add_file(batch.batch_id, "dummy_input.txt", io.BytesIO(content))
        manager.process_batch(batch.batch_id)

        paths = get_batch_paths(batch.batch_id)
        input_file = os.path.join(str(paths.input_dir), "dummy_input.txt")
        assert os.path.exists(input_file)

        importer = ImportService()
        result = importer.import_batch(batch.batch_id, memory_db)
        assert result.total_imported == 1

        # Raw dummy input file should now be removed from storage
        assert not os.path.exists(input_file)

