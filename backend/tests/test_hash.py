"""
Tests for SHA-256 streaming hashing service.
"""

import hashlib
import os
import pytest
from app.services.hash import StreamingHasher, compute_file_hash
from tests.conftest import create_test_file


class TestStreamingHasher:
    def test_streaming_hasher_matches_standard_hashlib(self):
        data = b"Hello, APBS Processor! " * 1000
        hasher = StreamingHasher()
        
        # Stream in 64-byte chunks
        chunk_size = 64
        for i in range(0, len(data), chunk_size):
            hasher.update(data[i:i + chunk_size])
            
        expected = hashlib.sha256(data).hexdigest()
        assert hasher.hexdigest() == expected
        assert hasher.bytes_processed == len(data)

    def test_hasher_copy(self):
        hasher = StreamingHasher()
        hasher.update(b"Part 1")
        
        copy_hasher = hasher.copy()
        hasher.update(b"Part 2 - Original")
        copy_hasher.update(b"Part 2 - Copy")
        
        assert hasher.hexdigest() != copy_hasher.hexdigest()

    def test_compute_file_hash(self):
        lines = ["Line 1", "Line 2", "Line 3"]
        file_path = create_test_file(lines)
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            expected = hashlib.sha256(content).hexdigest()
            assert compute_file_hash(file_path) == expected
        finally:
            os.unlink(file_path)
