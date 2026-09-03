"""
Streaming Record Separator for APBS 177-Character Fixed-Width Records.

This module provides a generator that yields records from input files,
automatically detecting whether records are:
  1. Continuous stream (no newlines) - 177-char fixed-width blocks
  2. Newline-delimited (legacy) - standard line-by-line format

The separator handles memory-efficient streaming with buffering,
ensuring large files don't load entirely into RAM.
"""

from __future__ import annotations

import io
from typing import BinaryIO, Iterator, TextIO, Union


def stream_apbs_records(
    file_handle: Union[TextIO, BinaryIO],
    record_length: int = 177,
    buffer_size: int = 65536,
) -> Iterator[tuple[int, str]]:
    """
    Generator that yields (record_number, record_string) tuples from an APBS file.
    
    Auto-detects file format:
      - Continuous stream (no newlines): Fixed 177-character blocks
      - Newline-delimited: Standard line-by-line (legacy format)
    
    Args:
        file_handle: An open file handle (text mode or binary mode).
        record_length: Expected length of each record (default 177 for APBS).
        buffer_size: Size of internal buffer for streaming (default 65536 bytes).
    
    Yields:
        Tuples of (record_number, record_string) where record_number is 1-based.
    
    Behavior:
      - For continuous streams: yields exactly record_length characters per record.
      - For newline-delimited: yields lines stripped of \\r\\n.
      - Trailing partial records (< record_length) are still yielded to allow
        the validator to flag them as INVALID_RECORD_LENGTH.
    """
    record_number = 0
    
    # Determine if file is text or binary and ensure we work with strings
    if isinstance(file_handle, io.TextIOBase):
        text_file = file_handle
    else:
        # Convert binary to text
        text_file = io.TextIOWrapper(file_handle, encoding='utf-8')
    
    # ── Auto-detect file format ─────────────────────────────────────
    # Peek at the beginning to determine if records are newline-delimited or continuous
    initial_chunk = text_file.read(buffer_size)
    if not initial_chunk:
        return  # Empty file
    
    # Detect format by checking if there's a newline within or near the first record
    # If there's a newline character in the first record_length+10 chars, it's likely newline-delimited
    peek_size = min(record_length + 50, len(initial_chunk))
    peek_content = initial_chunk[:peek_size]
    
    # Find all newline positions
    newline_positions = []
    if '\n' in peek_content:
        newline_positions.append(peek_content.find('\n'))
    if '\r' in peek_content:
        newline_positions.append(peek_content.find('\r'))
    
    # Determine if this is newline-delimited
    # If a newline appears at or before record_length, it's newline-delimited
    is_newline_delimited = False
    if newline_positions:
        first_newline_pos = min(newline_positions)
        # If newline appears within the first record (position < record_length) or at boundary (==),
        # it's newline-delimited
        if first_newline_pos <= record_length:
            is_newline_delimited = True
    
    if is_newline_delimited:
        # ── Newline-Delimited Mode (Legacy) ────────────────────────
        # Stream line-by-line with constant memory using chunk boundaries
        remainder = ""
        
        # Process the initial_chunk first
        for line in initial_chunk.splitlines(True):
            if line.endswith('\n') or line.endswith('\r'):
                record_number += 1
                yield (record_number, line.rstrip('\r\n'))
            else:
                remainder = line  # partial line at end of chunk
        
        # Stream remaining file in chunks (constant memory)
        for chunk in iter(lambda: text_file.read(buffer_size), ''):
            data = remainder + chunk
            remainder = ""
            for line in data.splitlines(True):
                if line.endswith('\n') or line.endswith('\r'):
                    record_number += 1
                    yield (record_number, line.rstrip('\r\n'))
                else:
                    remainder = line  # partial line at end of chunk
        
        # Yield any remaining partial line at EOF
        if remainder.strip():
            record_number += 1
            yield (record_number, remainder.rstrip('\r\n'))
    else:
        # ── Continuous Stream Mode (Fixed-Width) ───────────────────
        # Yield exactly record_length characters at a time
        buffer = initial_chunk
        
        while True:
            # Yield complete records from buffer
            while len(buffer) >= record_length:
                record_number += 1
                record = buffer[:record_length]
                buffer = buffer[record_length:]
                
                # Strip any trailing newlines/carriage returns that might be
                # between blocks in the continuous stream
                # (but preserve the full 177-char width if possible)
                yield (record_number, record)
            
            # Read more data
            chunk = text_file.read(buffer_size)
            if not chunk:
                # End of file: if there's a partial record, yield it
                if buffer.strip():
                    record_number += 1
                    yield (record_number, buffer)
                break
            
            buffer += chunk


def detect_file_format(file_path: str) -> str:
    """
    Detect whether a file is continuous stream or newline-delimited.
    
    Args:
        file_path: Path to the file to analyze.
    
    Returns:
        "continuous" for fixed-width continuous streams, "newline-delimited" for line-based.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        initial = f.read(1024)
    
    if not initial:
        return "empty"
    
    # Check for newlines within the first record
    peek_size = min(177 + 50, len(initial))
    peek = initial[:peek_size]
    
    # Find first newline
    newline_positions = []
    if '\n' in peek:
        newline_positions.append(peek.find('\n'))
    if '\r' in peek:
        newline_positions.append(peek.find('\r'))
    
    if newline_positions:
        first_newline = min(newline_positions)
        # If newline appears at or before the record length, it's newline-delimited
        if first_newline <= 177:
            return "newline-delimited"
    
    return "continuous"

