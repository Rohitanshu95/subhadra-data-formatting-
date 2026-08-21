"""
Tests for database models, constraints, and relationships.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.db_models import DBBatch, DBDuplicateLog, DBFile, DBTransaction


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    yield db
    db.close()


class TestDBModels:
    def test_create_batch_and_file_relationship(self, test_db):
        batch = DBBatch(
            batch_uuid="BATCH-20260820-001-TEST",
            status="READY",
            total_files=1,
        )
        test_db.add(batch)
        test_db.commit()
        test_db.refresh(batch)

        file = DBFile(
            batch_id=batch.id,
            filename="test_file.txt",
            sanitized_filename="test_file.txt",
            sha256="dummy_hash_12345",
            status="READY",
        )
        test_db.add(file)
        test_db.commit()

        assert len(batch.files) == 1
        assert batch.files[0].filename == "test_file.txt"

    def test_unique_record_hash_constraint(self, test_db):
        tx1 = DBTransaction(
            record_hash="duplicate_record_hash_123",
            batch_id="BATCH-001",
            file_id="file1",
            apbs_transaction_code="77",
            destination_bank_iin="123456789",
            beneficiary_aadhaar_number="123456789012345",
            sponsor_bank_iin="987654321",
            user_number="USR0001",
            user_credit_reference="REF0000000001",
            amount="0000000150000",
            item_sequence_number="0000000001",
            checksum="1234567890",
            success_flag="1",
            reason_code="00",
        )
        test_db.add(tx1)
        test_db.commit()

        # Adding another transaction with identical record_hash should violate unique constraint
        tx2 = DBTransaction(
            record_hash="duplicate_record_hash_123",
            batch_id="BATCH-002",
            file_id="file2",
            apbs_transaction_code="77",
            destination_bank_iin="123456789",
            beneficiary_aadhaar_number="123456789012345",
            sponsor_bank_iin="987654321",
            user_number="USR0001",
            user_credit_reference="REF0000000001",
            amount="0000000150000",
            item_sequence_number="0000000001",
            checksum="1234567890",
            success_flag="1",
            reason_code="00",
        )
        test_db.add(tx2)
        with pytest.raises(Exception):
            test_db.commit()
