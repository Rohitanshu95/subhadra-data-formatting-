"""
Cleanup script to remove all test records and data.

Clears:
1. Test files from storage directories (input, output, errors, logs)
2. Test batch/file records from the database
"""

import os
import shutil
from pathlib import Path
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.db_models import DBBatch, DBFile, DBTransaction

# Storage directories to clean
STORAGE_DIRS = [
    os.path.join(settings.STORAGE_BASE_DIR, "input"),
    os.path.join(settings.STORAGE_BASE_DIR, "output"),
    os.path.join(settings.STORAGE_BASE_DIR, "errors"),
    os.path.join(settings.STORAGE_BASE_DIR, "logs"),
]


def clean_storage_directories():
    """Remove all test files from storage directories."""
    print("\n" + "=" * 85)
    print("[CLEANUP] Cleaning storage directories...")
    print("=" * 85)
    
    total_removed = 0
    
    for storage_dir in STORAGE_DIRS:
        if not os.path.exists(storage_dir):
            print(f"[SKIP] {storage_dir} does not exist")
            continue
        
        dir_removed = 0
        for item in os.listdir(storage_dir):
            item_path = os.path.join(storage_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
                dir_removed += 1
                total_removed += 1
            except Exception as e:
                print(f"[ERROR] Failed to remove {item_path}: {e}")
        
        print(f"[OK] {storage_dir}: Removed {dir_removed} items")
    
    return total_removed


def clean_database():
    """Remove all test batch/file records from database."""
    print("\n" + "=" * 85)
    print("[CLEANUP] Cleaning database records...")
    print("=" * 85)
    
    session = SessionLocal()
    try:
        # Count before cleanup
        batch_count = session.query(DBBatch).count()
        file_count = session.query(DBFile).count()
        transaction_count = session.query(DBTransaction).count()
        
        print(f"[INFO] Before cleanup: {batch_count} batches, {file_count} files, {transaction_count} transactions")
        
        # Delete all transactions
        deleted_transactions = session.query(DBTransaction).delete(synchronize_session=False)
        print(f"[OK] Deleted {deleted_transactions} transaction records")
        
        # Delete all files (cascade will handle relationship cleanup)
        deleted_files = session.query(DBFile).delete(synchronize_session=False)
        print(f"[OK] Deleted {deleted_files} file records")
        
        # Delete all batches
        deleted_batches = session.query(DBBatch).delete(synchronize_session=False)
        print(f"[OK] Deleted {deleted_batches} batch records")
        
        # Commit transaction
        session.commit()
        
        # Count after cleanup
        batch_count_after = session.query(DBBatch).count()
        file_count_after = session.query(DBFile).count()
        transaction_count_after = session.query(DBTransaction).count()
        
        print(f"[INFO] After cleanup: {batch_count_after} batches, {file_count_after} files, {transaction_count_after} transactions")
        
        return deleted_batches, deleted_files, deleted_transactions
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Database cleanup failed: {e}")
        raise
    finally:
        session.close()


def main():
    """Execute full cleanup."""
    print("\n" + "=" * 85)
    print("[CLEANUP] Starting Full Test Data Cleanup")
    print("=" * 85)
    
    try:
        # Clean storage
        storage_removed = clean_storage_directories()
        
        # Clean database
        batches_removed, files_removed, transactions_removed = clean_database()
        
        # Summary
        print("\n" + "=" * 85)
        print("[CLEANUP] Cleanup Complete!")
        print("=" * 85)
        print(f"  * Storage items removed: {storage_removed}")
        print(f"  * Batch records removed: {batches_removed}")
        print(f"  * File records removed: {files_removed}")
        print(f"  * Transaction records removed: {transactions_removed}")
        print("=" * 85 + "\n")
        
    except Exception as e:
        print(f"\n[FATAL ERROR] Cleanup failed: {e}")
        raise


if __name__ == "__main__":
    main()
