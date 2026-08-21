# APBS 177-Character Fixed-Width Processing & Validation System
## Development Roadmap & Implementation Phases

Based on the architecture defined in [plan.txt](plan.txt), this document outlines the end-to-end development roadmap structured into 7 distinct, progressive phases.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Phase 1   │────▶│   Phase 2   │────▶│   Phase 3   │────▶│   Phase 4   │
│ Core Parser │     │ Batch & Dups│     │ Queue Worker│     │ Verification│
│ & Streaming │     │ File Hashing│     │ Celery/Redis│     │ & DB Import │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
┌─────────────┐     ┌─────────────┐     ┌─────────────┐            │
│   Phase 7   │◀────│   Phase 6   │◀────│   Phase 5   │◀───────────┘
│ Security &  │     │ Real-time UI│     │ Human Check │
│ Deployment  │     │ & Dashboard │     │ & Approvals │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## Phase 1: Core APBS Parsing Engine & Streaming I/O (Vertical Slice)
**Objective:** Prove the 177-character fixed-width parsing, 17-field schema validation, and streaming I/O without loading full files into memory.

### Key Components & Tasks:
- **Centralized Schema Definition (`backend/app/services/apbs_parser.py`):**
  - Offset and width table for all 17 fields (Transaction Code, Bank IINs, Aadhaar, Amount, Checksum, Success Flag, Reason Code, etc.).
  - Non-credit line detector (e.g., skip header/trailer records with transaction code `33` without raising parse errors).
- **Streaming Line Reader & Validator (`backend/app/services/validation.py`):**
  - Chunked/buffered streaming line reader with strict 177-character length validation (`INVALID_RECORD_LENGTH` handling).
  - Field-level type validators (Numeric, Alphanumeric, Paise amount conversion).
- **Output Generator (`backend/app/services/output.py`):**
  - Streaming generation of clean, delimited `.txt` output per file.
  - Streaming generation of error records `.txt` with line numbers and failure reasons.
- **Unit & Property Testing:**
  - Automated tests covering valid records, malformed lines, truncated files, and non-credit lines.

### Acceptance Criteria:
- A 100 MB test file processes in constant low memory (< 50 MB RAM).
- Invalid lines are logged with line numbers and processing never crashes mid-file.

---

## Phase 2: Batch Management & File-Level Content Hashing
**Objective:** Support streaming multi-file uploads (up to 100 files / 3 GB) with content-based SHA-256 deduplication.

### Key Components & Tasks:
- **Storage Layout Setup (`storage/`):**
  - Scaffold directories: `storage/input/{batch_id}/`, `output/`, `errors/`, and `logs/`.
- **Streaming Upload Service (`backend/app/services/upload.py`, `backend/app/services/hash.py`):**
  - Single-pass streaming upload calculating content SHA-256 on the fly without secondary disk re-reads.
  - Path traversal protection and filename sanitization.
- **Metadata Models (`backend/app/models/batch.py`, `backend/app/models/file.py`):**
  - Batch entity (`id`, `batch_uuid`, `status`, `total_files`, `total_size`).
  - File entity (`id`, `sha256`, `status`, `record_count`, `valid_count`, `duplicate_count`).
- **File Deduplication Engine (`backend/app/services/duplicate.py`):**
  - Look up file SHA-256 against previous records; flag exact duplicates as `DUPLICATE_FILE` and skip re-parsing.

### Acceptance Criteria:
- Re-uploading an existing file under a modified filename is identified as a duplicate and skipped.
- Batch directory structure is initialized cleanly upon batch creation.

---

## Phase 3: Asynchronous Task Queue & Controlled Worker Pool
**Objective:** Decouple file processing from HTTP requests using Celery + Redis with configurable concurrency.

### Key Components & Tasks:
- **Celery & Redis Integration (`backend/app/workers/file_worker.py`):**
  - Bounded concurrency worker pool (`WORKER_COUNT=4` configurable).
  - Worker tasks for individual file streaming, parsing, hashing, and output generation.
- **Batch State Coordinator:**
  - Progress counters: total files processed, records valid/invalid/duplicate.
  - Batch completion aggregator (`COMPLETED` vs. `COMPLETED_WITH_ERRORS` hierarchy).
- **Batch Summary Generator (`storage/logs/{batch_id}/batch_summary.txt`):**
  - Automated generation of file-by-file metrics and aggregated batch summary.
- **REST Endpoints (`backend/app/api/batches.py`):**
  - `POST /api/batches` (Create batch)
  - `POST /api/batches/{id}/upload` (Stream upload)
  - `POST /api/batches/{id}/process` (Enqueue background processing)
  - `GET /api/batches/{id}` & `GET /api/batches/{id}/progress` (Status checks)

### Acceptance Criteria:
- Uploading 50+ files triggers background queue execution with maximum `N` concurrent file workers.
- One corrupted file does not interrupt remaining files in the batch.

---

## Phase 4: Record-Level Hashing & Idempotent SQL Import
**Objective:** Implement record-level SHA-256 identity, database schemas, and bulk idempotent database commit.

### Key Components & Tasks:
- **Database Schema Migrations (PostgreSQL/SQL):**
  - Tables: `batches`, `files`, `transactions` (`record_hash UNIQUE`), `duplicates_log`, `logs`.
- **Record Normalization & Hashing (`backend/app/services/hash.py`):**
  - Generate `record_hash = SHA256(normalized_177_char_line)` for every valid record.
- **Bulk Database Importer (`backend/app/services/import.py`):**
  - Chunked bulk inserts (e.g., 5,000–10,000 rows/batch) using `ON CONFLICT (record_hash) DO NOTHING`.
  - Conflict detection routing: write duplicate attempts into `duplicates_log` linked to `attempted_batch_id` and original transaction.
- **Database Performance Tuning:**
  - B-tree indexing on `record_hash`, `batch_id`, and `created_at`.

### Acceptance Criteria:
- 1,000,000 records imported in bulk chunks without locking or timeouts.
- Re-running the import on overlapping data inserts only new records and logs duplicates in `duplicates_log`.

---

## Phase 5: Human Verification Checkpoint & Batch Reports
**Objective:** Ensure no raw/unverified data touches SQL until human review and approval.

### Key Components & Tasks:
- **Human Verification Flow (`POST /api/batches/{id}/verify`):**
  - Lock batch into `AWAITING_VERIFICATION` state upon worker completion.
  - Provide sample records inspection, error previews, and summary metrics.
- **Report & Artifact Downloads (`GET /api/batches/{id}/download`):**
  - Download endpoints for clean TXT output, error logs, and batch summaries.
- **Explicit Commit Endpoint (`POST /api/batches/{id}/import`):**
  - Triggers the database import service only when explicitly approved by an authorized user.

### Acceptance Criteria:
- Data remains strictly in file storage until the `/verify` and `/import` flow is executed.

---

## Phase 6: Frontend Application (React + Vite + Real-Time Tracking)
**Objective:** Build the responsive, intuitive UI with live WebSocket/SSE progress updates.

### Key Components & Tasks:
- **Core UI Scaffolding (`frontend/src/`):**
  - Setup React + Vite, routing, and styling system.
- **Key Pages:**
  - `/batches/new`: Multi-file drag-and-drop uploader with pre-checks (≤ 100 files, ≤ 3 GB).
  - `/batches/:id`: Live progress bar (files %, records valid/invalid/duplicate, worker activity via WebSocket).
  - `/batches/:id/results`: Verification checkpoint screen with summary tables, sample record viewer, and download links.
  - `/dashboard`: Overall system statistics (total batches, daily records processed, duplicate rates).
  - `/batches/:id/logs`: Real-time streaming log viewer.

### Acceptance Criteria:
- WebSocket connection streams progress dynamically without requiring page refreshes.
- Clear visual distinction between Clean Records, Invalid Records, and Duplicate Records.

---

## Phase 7: Security Hardening, PII Masking & Production Deployment
**Objective:** Ensure data security, compliance with Aadhaar/PII masking standards, and production-ready containerization.

### Key Components & Tasks:
- **PII Masking Layer (`backend/app/utils/masking.py`, `backend/app/core/logging.py`):**
  - Aadhaar masking (`********9012`) and Bank Account masking (`*******3456`) across all application logs and frontend previews.
- **Authentication & Authorization:**
  - JWT-based auth (`/api/auth/login`), role permissions, and request rate-limiting.
  - Full audit trail logging for all batch creation, verification, and DB import actions.
- **Data Retention & Lifecycle Management:**
  - Configurable retention cleanup job for raw input files after verification window expires.
- **Containerization & Deployment (`docker/`, `docker-compose.yml`):**
  - Multi-stage Dockerfiles for FastAPI backend and React frontend.
  - Nginx reverse proxy configuration with client body size tuned for 3 GB uploads.
  - Celery + Redis + Database services in `docker-compose`.

### Acceptance Criteria:
- No unmasked Aadhaar or bank account numbers appear in any log files.
- `docker-compose up` launches the complete stack (API, UI, Redis, Celery, DB, Nginx) ready for end-to-end processing.
