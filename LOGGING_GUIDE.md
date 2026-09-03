# Processing Logs & Terminal Output Guide

## Complete Logging Overview

Your application now has **comprehensive logging** at every stage of file processing. All logs print to the terminal where you run the backend server.

---

## Where to See Logs

### Option 1: Terminal Running Uvicorn (Recommended)
```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

All logs will print here in real-time:
- ✅ File processing progress
- ✅ Record validation details  
- ✅ Batch completion summary
- ✅ Error messages

---

## Logging Stages

### Stage 1: Batch Starts Processing
```
==========================================================================================
[BATCH WORKER] 🚀 Starting Batch Processing: BATCH-20260903-001
==========================================================================================
[BATCH WORKER] 📋 Files to Process: 2 out of 2 total
  1. file_20260901_001.txt (1,234,567 bytes)
  2. file_20260901_002.txt (2,345,678 bytes)
[BATCH WORKER] ⏳ Queued: file_20260901_001.txt (Task ID: abc-123-def-456)
[BATCH WORKER] ⏳ Queued: file_20260901_002.txt (Task ID: xyz-789-uvw-012)
==========================================================================================
```

### Stage 2: Individual File Processing

#### File Starts
```
[WORKER] [TASK] 📥 Processing Batch: BATCH-20260903-001 | File: file_20260901_001.txt
[WORKER] [INFO] File Details: 1,234,567 bytes | Status: READY
[WORKER] [START] Beginning file processing...
```

#### Live Progress (Every 5,000 records)
```
[STREAM PARSER] [HEADER] Record 0001: Headings row detected (177 chars) -> Skipped
[PARSER] [INFO]  Record 0002: Length 176 chars, padded to 177
[PARSER] [INFO]  Record 0003: Length 200 chars, truncated to 177
[PARSER] [WARN]  Record 0004: Validation Warning(s) -> beneficiary_aadhaar_number: Invalid length
...
[STREAM PARSER] [PROGRESS] file_20260901_001.txt -> 5,000 records processed (5,000 clean, 0 invalid)...
[STREAM PARSER] [PROGRESS] file_20260901_001.txt -> 10,000 records processed (10,000 clean, 5 invalid)...
[STREAM PARSER] [PROGRESS] file_20260901_001.txt -> 15,000 records processed (15,000 clean, 12 invalid)...
```

#### File Completion Summary
```
-----------
[WORKER] [FILE COMPLETE] file_20260901_001.txt
  ✓ Total Lines Read      : 23,456
  ✓ Valid Records         : 23,445
  ✓ Validation Warnings   : 11
  ✓ Skipped Headers/Etc   : 0
  ✓ Output File           : storage/output/file_20260901_001_output.txt
  ✓ Processing Mode       : LENIENT (accept all data as-is)
-----------
```

### Stage 3: Batch Completion

Once **all files** in the batch are processed:

```
==========================================================================================
[WORKER] [COMPLETE] Batch BATCH-20260903-001 Processing Finished!
==========================================================================================
  ✓ Batch Status          : COMPLETED
  ✓ Total Files Processed : 2
  ✓ Total Valid Records   : 45,890
  ✓ Total Invalid Records : 23
  ✓ Total Skipped Lines   : 2
  ✓ Success Rate          : 99.95%

File Details:
    📄 file_20260901_001.txt
       - Status: COMPLETED
       - Valid Records: 23,445 | Invalid: 11 | Skipped: 0
       - Output: storage/output/file_20260901_001_output.txt
    📄 file_20260901_002.txt
       - Status: COMPLETED
       - Valid Records: 22,445 | Invalid: 12 | Skipped: 2
       - Output: storage/output/file_20260901_002_output.txt

[WORKER] [SUMMARY] Batch summary report generated at storage/logs/BATCH-20260903-001/batch_summary.txt
==========================================================================================
```

---

## Log Levels & Indicators

| Indicator | Meaning | Example |
|-----------|---------|---------|
| 🚀 | Batch starting | `🚀 Starting Batch Processing` |
| 📋 | File list/info | `📋 Files to Process: 2` |
| 📥 | File processing | `📥 Processing Batch` |
| ⏳ | Task queued | `⏳ Queued: filename.txt` |
| ✓ | Success/valid | `✓ Valid Records: 23,445` |
| ⚠️ | Warning | `⚠️ File not in READY state` |
| ❌ | Error | `❌ Error processing file` |
| 📄 | File details | `📄 filename.txt` |

---

## Lenient Processing Mode Output

Since you're using **LENIENT mode** (default), the logs show:

```
[PARSER] [WARN]  Record 0045: Validation Warning(s) -> beneficiary_name: Contains special characters ;>/@
  ✓ Records are ACCEPTED despite warnings
  ✓ All data is PRESERVED as-is
  ✓ No records REJECTED
  ✓ Processing Mode: LENIENT
```

---

## File Output Locations

All processed data is saved here:

```
project-root/
└── storage/
    ├── input/           # Your uploaded files
    ├── output/          # Processed, clean records
    │   ├── file_001_output.txt
    │   └── file_002_output.txt
    ├── errors/          # Error files (if any)
    │   ├── file_001_errors.txt
    │   └── file_002_errors.txt
    └── logs/
        └── BATCH-20260903-001/
            ├── batch_summary.txt
            └── processing_log.txt
```

---

## What the Logs Show

### ✅ For Each Record
- **Status**: Valid, Warning, or Error
- **Length**: Auto-padded or truncated
- **Content**: Special characters preserved (lenient mode)
- **Issues**: Any validation warnings logged

### ✅ For Each File
- **Total lines read**
- **Valid records**
- **Validation warnings**
- **Skipped headers**
- **Output file path**
- **Processing duration** (implicit by log timestamps)

### ✅ For Each Batch
- **Total files processed**
- **Total valid records across all files**
- **Total validation warnings**
- **Overall success rate percentage**
- **Batch summary report location**

---

## Example: Complete Processing Flow

```
[Batch starts]
  ↓
[Batch: 2 files queued]
  ↓
[File 1: processing starts]
  ├─ Progress: 5,000 records ✓
  ├─ Progress: 10,000 records ✓
  ├─ Progress: 15,000 records ✓
  └─ File 1: COMPLETE (23,445 valid)
  ↓
[File 2: processing starts]
  ├─ Progress: 5,000 records ✓
  ├─ Progress: 10,000 records ✓
  └─ File 2: COMPLETE (22,445 valid)
  ↓
[Batch: FINISHED]
  └─ Summary: 45,890 total records ✓
```

---

## Troubleshooting Logs

### Issue: Records being padded
```
[PARSER] [INFO]  Record 0045: Length 150 chars, padded to 177
```
**Reason**: Record shorter than 177 characters (lenient mode pads with spaces)

### Issue: Records being truncated
```
[PARSER] [INFO]  Record 0089: Length 250 chars, truncated to 177
```
**Reason**: Record longer than 177 characters (lenient mode truncates)

### Issue: Validation warnings
```
[PARSER] [WARN]  Record 0123: Validation Warning(s) -> amount: Non-numeric content
```
**Reason**: Field contains unexpected characters (lenient mode accepts anyway)

### Issue: File not processed
```
[WORKER] [SKIP] ⚠️  File filename.txt not in READY state (current: FAILED). Skipping.
```
**Reason**: File failed validation or upload; check earlier logs

---

## Tips for Reading Logs

1. **Look for 🚀 symbols** - These mark major processing stages
2. **Check success rate %** - Shows overall data quality
3. **Count the progress lines** - Each one = 5,000 records processed
4. **Find ❌ errors** - Search for this symbol to find problems
5. **Timestamp each log** - Your terminal shows timestamps

---

## Running Continuously

To keep the backend running and monitoring logs:

```powershell
# Terminal 1: Start Backend
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Terminal 2: Upload & Process via Dashboard
# Terminal 2 will show all processing logs in real-time from Terminal 1
```

---

## Log File Persistence

Logs are also saved in:
```
storage/logs/{BATCH_ID}/batch_summary.txt
```

This file contains:
- Complete batch statistics
- File-by-file breakdown
- Timestamp of processing
- Success/failure details

---

## Summary

✅ **All processing is logged to the terminal**  
✅ **Logs show real-time progress every 5,000 records**  
✅ **Batch completion shows comprehensive statistics**  
✅ **Special symbols & lenient mode clearly indicated**  
✅ **Output file paths shown for verification**

**Just watch the terminal while processing!** 🚀
