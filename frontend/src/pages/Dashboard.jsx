import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { 
  PlusCircle, 
  Layers, 
  CheckCircle2, 
  AlertTriangle, 
  CopyCheck, 
  ArrowRight,
  Database,
  RefreshCw,
  FileText,
  Clock,
  Terminal,
  Table,
  Search,
  Filter,
  Shield,
  X,
  Trash2
} from 'lucide-react';
import { listBatches, getOverviewStats, getParsedRecords, deleteBatch, deleteRecord } from '../services/api';
import MetricCard from '../components/MetricCard';
import StatusBadge from '../components/StatusBadge';
import Modal from '../components/Modal';
import Toast from '../components/Toast';

export default function Dashboard() {
  const [activeView, setActiveView] = useState('records'); // 'records' (default primary) or 'batches'
  const [batches, setBatches] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  // Records state
  const [records, setRecords] = useState([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalPages, setTotalPages] = useState(1);
  const [dataSource, setDataSource] = useState('Production Database & Staging Records');
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  // Dynamic Filters for Records
  const [selectedBatch, setSelectedBatch] = useState('ALL');
  const [successFlag, setSuccessFlag] = useState('');
  const [reasonCode, setReasonCode] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Debounce search input for instant dynamic filtering
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch overview stats and batch list
  const fetchOverviewData = async () => {
    try {
      setLoading(true);
      const [batchesData, statsData] = await Promise.all([
        listBatches(),
        getOverviewStats().catch(() => null),
      ]);
      setBatches(batchesData || []);
      setStats(statsData);
    } catch (err) {
      console.error("Failed to load overview data", err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch parsed records dynamically
  const fetchRecordsData = useCallback(async () => {
    try {
      setRecordsLoading(true);
      const params = {
        page,
        page_size: pageSize,
      };
      if (successFlag !== '') params.success_flag = successFlag;
      if (reasonCode.trim() !== '') params.reason_code = reasonCode.trim();
      if (statusFilter !== 'ALL') params.status = statusFilter;
      if (debouncedSearch.trim() !== '') params.search = debouncedSearch.trim();

      const batchTarget = selectedBatch && selectedBatch !== 'ALL' ? selectedBatch : 'all';
      const data = await getParsedRecords(batchTarget, params);
      setRecords(data.records || []);
      setTotalRecords(data.total || 0);
      setTotalPages(data.total_pages || 1);
      setDataSource(data.data_source || 'Production Database & Staging');
    } catch (err) {
      console.error("Failed to load parsed records", err);
    } finally {
      setRecordsLoading(false);
    }
  }, [selectedBatch, page, pageSize, successFlag, reasonCode, statusFilter, debouncedSearch]);

  useEffect(() => {
    fetchOverviewData();
  }, []);

  useEffect(() => {
    fetchRecordsData();
  }, [fetchRecordsData]);

  const handleClearFilters = () => {
    setSelectedBatch('ALL');
    setSuccessFlag('');
    setReasonCode('');
    setStatusFilter('ALL');
    setSearchQuery('');
    setDebouncedSearch('');
    setPage(1);
  };

  const [modalConfig, setModalConfig] = useState({
    isOpen: false,
    title: '',
    description: '',
    confirmText: 'Delete',
    variant: 'danger',
    details: null,
    onConfirm: null,
  });
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const closeModal = () => {
    setModalConfig(prev => ({ ...prev, isOpen: false }));
  };

  // Batch deletion handler with custom Modal
  const promptDeleteBatch = (batchId) => {
    setModalConfig({
      isOpen: true,
      title: 'Delete Batch Confirmation',
      description: 'Are you sure you want to permanently delete this batch? All transactions, audit logs, and physical files will be permanently erased.',
      confirmText: 'Delete Entire Batch',
      variant: 'danger',
      details: (
        <div>
          <div style={{ marginBottom: '4px' }}><strong>Batch Identifier:</strong> <span style={{ fontFamily: 'var(--font-mono)' }}>{batchId}</span></div>
          <div style={{ color: '#b91c1c', fontSize: '0.8rem' }}>⚠️ This action will remove all corresponding SQL database transactions and storage artifacts.</div>
        </div>
      ),
      onConfirm: async () => {
        try {
          setDeletingId(batchId);
          await deleteBatch(batchId);
          showToast(`Batch "${batchId}" and associated records deleted.`);
          closeModal();
          await Promise.all([fetchOverviewData(), fetchRecordsData()]);
        } catch (err) {
          showToast(`Failed to delete batch: ${err.response?.data?.detail || err.message}`, 'error');
        } finally {
          setDeletingId(null);
        }
      }
    });
  };

  // Record deletion handler with custom Modal
  const promptDeleteRecord = (record) => {
    const beneficiary = record.beneficiary_name?.trim() || 'Beneficiary Record';
    const ref = record.user_credit_reference || 'N/A';
    const aadhaar = record.beneficiary_aadhaar_number || 'N/A';
    const amount = record.amount || '0';

    setModalConfig({
      isOpen: true,
      title: 'Delete APBS Transaction',
      description: 'Are you sure you want to permanently remove this transaction from the database and staging files?',
      confirmText: 'Delete Record',
      variant: 'danger',
      details: (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <div><strong>Beneficiary:</strong> {beneficiary}</div>
          <div><strong>Credit Ref:</strong> <span style={{ fontFamily: 'var(--font-mono)' }}>{ref}</span></div>
          <div><strong>Aadhaar:</strong> <span style={{ fontFamily: 'var(--font-mono)' }}>{aadhaar}</span></div>
          <div><strong>Amount (Paise):</strong> {amount}</div>
        </div>
      ),
      onConfirm: async () => {
        try {
          const recId = record.id || record.user_credit_reference;
          setDeletingId(recId);
          await deleteRecord(recId, {
            ref: record.user_credit_reference,
            batch_id: record.batch_id,
          });
          showToast(`Transaction for "${beneficiary}" deleted from database.`);
          closeModal();
          await Promise.all([fetchOverviewData(), fetchRecordsData()]);
        } catch (err) {
          showToast(`Failed to delete record: ${err.response?.data?.detail || err.message}`, 'error');
        } finally {
          setDeletingId(null);
        }
      }
    });
  };

  const hasActiveFilters = selectedBatch !== 'ALL' || successFlag !== '' || reasonCode !== '' || statusFilter !== 'ALL' || searchQuery !== '';

  // Reconciled pipeline stage calculations
  const totalParsed = stats?.total_records_parsed ?? batches.reduce((acc, b) => acc + (b.total_records || 0), 0);
  const awaitingVerification = stats?.awaiting_verification ?? batches.reduce((acc, b) => {
    if (['COMPLETED', 'COMPLETED_WITH_ERRORS', 'AWAITING_VERIFICATION', 'VERIFIED'].includes(b.status)) {
      return acc + (b.valid_records || 0);
    }
    return acc;
  }, 0);
  const committedToDb = stats?.committed_to_db ?? stats?.db_transactions_count ?? batches.reduce((acc, b) => {
    if (b.status === 'IMPORTED') return acc + (b.db_committed_count || b.valid_records || 0);
    return acc;
  }, 0);
  const duplicatesSkipped = stats?.duplicates_skipped ?? ((stats?.db_duplicates_count || 0) + batches.reduce((acc, b) => acc + (b.duplicate_files || 0), 0));
  const failedRecords = stats?.failed_records ?? batches.reduce((acc, b) => acc + (b.invalid_records || 0), 0);

  const getRecordStatusBadge = (status) => {
    const s = (status || '').toUpperCase();
    if (s === 'COMMITTED') {
      return <span style={{ background: '#f0fdf4', color: '#15803d', border: '1px solid #bbf7d0', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>Committed</span>;
    }
    if (s === 'DUPLICATE') {
      return <span style={{ background: '#fffbeb', color: '#b45309', border: '1px solid #fde68a', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>Duplicate</span>;
    }
    if (s === 'INVALID') {
      return <span style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>Invalid</span>;
    }
    return <span style={{ background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>Pending Verification</span>;
  };

  const getDbPushBadge = (batch) => {
    const status = batch.status;
    if (status === 'IMPORTED') {
      const newCount = batch.db_committed_count || batch.valid_records || 0;
      const dupCount = batch.db_duplicates_count || 0;
      return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700, background: '#f0fdf4', color: '#15803d', border: '1px solid #bbf7d0' }}>
          <CheckCircle2 size={12} /> Committed ({newCount} new / {dupCount} dup)
        </span>
      );
    }
    if (status === 'VERIFIED') {
      return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700, background: '#faf5ff', color: '#7e22ce', border: '1px solid #e9d5ff' }}>
          <Clock size={12} /> Verified — Ready to Commit
        </span>
      );
    }
    if (status === 'FAILED') {
      return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700, background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca' }}>
          <AlertTriangle size={12} /> Failed
        </span>
      );
    }
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600, background: '#f8fafc', color: '#64748b', border: '1px solid #e2e8f0' }}>
        Not yet committed
      </span>
    );
  };

  return (
    <div className="app-container">
      {/* Header section */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '14px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', color: '#0f172a', marginBottom: '4px' }}>
            APBS Batch Processing Dashboard
          </h1>
          <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
            Aadhaar Payment Bridge System — 177-Character Fixed-Width Validation & DB Lifecycle Pipeline
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button 
            onClick={() => { fetchOverviewData(); fetchRecordsData(); }} 
            className="btn btn-secondary"
            title="Refresh"
          >
            <RefreshCw size={15} className={loading || recordsLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <Link to="/batches/new" className="btn btn-primary">
            <PlusCircle size={15} />
            Upload New Batch
          </Link>
        </div>
      </div>

      {/* 5 Pipeline-Stage Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '14px', marginBottom: '24px' }}>
        <MetricCard 
          title="Total Records Parsed" 
          value={totalParsed.toLocaleString()} 
          subtitle="Processed across all batches" 
          icon={Layers} 
          color="#1d4ed8" 
        />
        <MetricCard 
          title="Awaiting Verification" 
          value={awaitingVerification.toLocaleString()} 
          subtitle="Processed, pending review" 
          icon={Clock} 
          color="#7e22ce" 
        />
        <MetricCard 
          title="Committed to DB" 
          value={committedToDb.toLocaleString()} 
          subtitle="Unique records inserted in SQL" 
          icon={Database} 
          color="#15803d" 
        />
        <MetricCard 
          title="Duplicates Skipped" 
          value={duplicatesSkipped.toLocaleString()} 
          subtitle="File & record duplicate collisions" 
          icon={CopyCheck} 
          color="#b45309" 
        />
        <MetricCard 
          title="Failed / Invalid Records" 
          value={failedRecords.toLocaleString()} 
          subtitle="Schema & length violations" 
          icon={AlertTriangle} 
          color="#b91c1c" 
        />
      </div>

      {/* Main View Mode Selector Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', gap: '6px', background: '#e2e8f0', padding: '4px', borderRadius: '6px' }}>
          <button
            onClick={() => setActiveView('records')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              borderRadius: '4px',
              border: 'none',
              fontWeight: 700,
              fontSize: '0.875rem',
              cursor: 'pointer',
              background: activeView === 'records' ? '#ffffff' : 'transparent',
              color: activeView === 'records' ? '#1d4ed8' : '#64748b',
              boxShadow: activeView === 'records' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
            }}
          >
            <Table size={15} />
            Parsed APBS Records ({totalRecords.toLocaleString()})
          </button>

          <button
            onClick={() => setActiveView('batches')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              borderRadius: '4px',
              border: 'none',
              fontWeight: 700,
              fontSize: '0.875rem',
              cursor: 'pointer',
              background: activeView === 'batches' ? '#ffffff' : 'transparent',
              color: activeView === 'batches' ? '#1d4ed8' : '#64748b',
              boxShadow: activeView === 'batches' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
            }}
          >
            <Layers size={15} />
            Registered Batches ({batches.length})
          </button>
        </div>

        {activeView === 'records' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#166534', background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '4px 10px', borderRadius: '4px' }}>
            <CheckCircle2 size={15} color="#16a34a" />
            <span style={{ fontWeight: 600 }}>Full Unmasked Data View Active</span>
          </div>
        )}
      </div>

      {/* VIEW 1: PARSED RECORDS TABLE (PRIMARY DASHBOARD VIEW) */}
      {activeView === 'records' && (
        <>
          {/* Dynamic Records Filter Card */}
          <div className="gov-card" style={{ padding: '16px', marginBottom: '18px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', alignItems: 'end' }}>
              {/* Batch Filter Dropdown */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                  Filter by Batch
                </label>
                <select
                  value={selectedBatch}
                  onChange={(e) => { setSelectedBatch(e.target.value); setPage(1); }}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.875rem', backgroundColor: '#ffffff' }}
                >
                  <option value="ALL">All Registered Batches</option>
                  {batches.map((b) => (
                    <option key={b.batch_id} value={b.batch_id}>
                      {b.batch_id} ({b.status})
                    </option>
                  ))}
                </select>
              </div>

              {/* Status Filter */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                  Record Status
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.875rem', backgroundColor: '#ffffff' }}
                >
                  <option value="ALL">All Statuses</option>
                  <option value="Committed">Committed</option>
                  <option value="Duplicate">Duplicate</option>
                  <option value="Pending Verification">Pending Verification</option>
                  <option value="Invalid">Invalid</option>
                </select>
              </div>

              {/* Success Flag Filter */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                  Success Flag
                </label>
                <select
                  value={successFlag}
                  onChange={(e) => { setSuccessFlag(e.target.value); setPage(1); }}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.875rem', backgroundColor: '#ffffff' }}
                >
                  <option value="">All Flags</option>
                  <option value="1">1 — Credited</option>
                  <option value="0">0 — Returned / Failed</option>
                </select>
              </div>

              {/* Search Query */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                  Search (Aadhaar / Name / Ref / Bank)
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="text"
                    placeholder="Search in real-time..."
                    value={searchQuery}
                    onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
                    style={{ width: '100%', padding: '8px 10px 8px 30px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                  />
                  <Search size={14} color="#94a3b8" style={{ position: 'absolute', left: '10px', top: '10px' }} />
                  {searchQuery && (
                    <button
                      onClick={() => { setSearchQuery(''); setPage(1); }}
                      style={{ position: 'absolute', right: '8px', top: '8px', background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              </div>

              {/* Clear Action */}
              <div>
                <button 
                  type="button" 
                  onClick={handleClearFilters} 
                  className="btn btn-secondary"
                  disabled={!hasActiveFilters}
                  style={{ width: '100%', padding: '8px 14px' }}
                >
                  Clear Filters
                </button>
              </div>
            </div>

            {hasActiveFilters && (
              <div style={{ marginTop: '10px', fontSize: '0.8rem', color: '#1d4ed8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Filter size={12} />
                <span>Filters dynamically applied. Showing <strong>{totalRecords}</strong> matching record(s).</span>
              </div>
            )}
          </div>

          {/* 18-Column Parsed Records Table Card */}
          <div className="gov-card" style={{ padding: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Table size={18} color="#1d4ed8" />
                <h2 style={{ fontSize: '1.1rem', color: '#0f172a' }}>
                  Parsed Clean Records
                </h2>
                <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>
                  — 17-field canonical schema with complete Aadhaar & account numbers
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: '#64748b' }}>
                <span>Page {page} of {totalPages}</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                  style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.8rem' }}
                >
                  <option value={25}>25 / page</option>
                  <option value={50}>50 / page</option>
                  <option value={100}>100 / page</option>
                </select>
              </div>
            </div>

            {records.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px 20px', color: '#64748b', background: '#f8fafc', borderRadius: '4px' }}>
                <Database size={32} color="#94a3b8" style={{ margin: '0 auto 8px' }} />
                <p style={{ fontWeight: 600, color: '#1e293b' }}>No parsed records found</p>
                <p style={{ fontSize: '0.85rem' }}>Upload an APBS response file to begin parsing and reviewing data.</p>
                {hasActiveFilters && (
                  <button onClick={handleClearFilters} className="btn btn-secondary" style={{ marginTop: '10px' }}>
                    Reset Filters
                  </button>
                )}
              </div>
            ) : (
              <div className="table-container" style={{ maxHeight: '620px', overflowX: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th style={{ whiteSpace: 'nowrap' }}>#</th>
                      <th style={{ whiteSpace: 'nowrap' }}>TXN CODE (1)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>DEST BANK IIN (2)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>DEST ACC TYPE (3)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>LEDGER FOLIO (4)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>AADHAAR NUMBER (5)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>BENEFICIARY NAME (6)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>SPONSOR BANK IIN (7)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>USER NUMBER (8)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>NARRATION (9)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>CREDIT REFERENCE (10)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>AMOUNT (PAISE) (11)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>ITEM SEQ (12)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>CHECKSUM (13)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>SUCCESS FLAG (14)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>FILLER (15)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>REASON (16)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>DEST ACCOUNT NO (17)</th>
                      <th style={{ whiteSpace: 'nowrap', textAlign: 'center' }}>STATUS (18)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>SOURCE FILE</th>
                      <th style={{ whiteSpace: 'nowrap', textAlign: 'center' }}>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((r, idx) => (
                      <tr key={idx}>
                        <td style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{(page - 1) * pageSize + idx + 1}</td>
                        <td><span className="badge badge-ready">{r.apbs_transaction_code || '—'}</span></td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{r.destination_bank_iin || '—'}</td>
                        <td>{r.destination_account_type || '—'}</td>
                        <td>{r.ledger_folio_number || '—'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#1e293b' }}>
                          {r.beneficiary_aadhaar_number || '—'}
                        </td>
                        <td style={{ fontWeight: 600, color: '#0f172a', minWidth: '130px' }}>
                          {r.beneficiary_name || '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{r.sponsor_bank_iin || '—'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{r.user_number || '—'}</td>
                        <td style={{ fontSize: '0.8rem', color: '#475569' }}>{r.user_name_narration || '—'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{r.user_credit_reference || '—'}</td>
                        <td style={{ fontWeight: 700, color: '#15803d' }}>{r.amount || '—'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{r.item_sequence_number || '—'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{r.checksum || '—'}</td>
                        <td>
                          {r.success_flag === '1' || r.success_flag?.startsWith('1') ? (
                            <span style={{ color: '#15803d', fontWeight: 700 }}>1 (Credited)</span>
                          ) : r.success_flag === '0' || r.success_flag?.startsWith('0') ? (
                            <span style={{ color: '#b91c1c', fontWeight: 700 }}>0 (Returned)</span>
                          ) : (
                            r.success_flag || '—'
                          )}
                        </td>
                        <td style={{ color: '#94a3b8' }}>{r.filler || '—'}</td>
                        <td><strong>{r.reason_code || '—'}</strong></td>
                        <td style={{ fontFamily: 'var(--font-mono)', color: '#334155' }}>
                          {r.destination_bank_account_number || '—'}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          {getRecordStatusBadge(r.status)}
                        </td>
                        <td style={{ fontSize: '0.75rem', color: '#64748b' }}>
                          {r._source_file || r.batch_id || '—'}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button
                            onClick={() => promptDeleteRecord(r)}
                            disabled={deletingId === (r.id || r.user_credit_reference)}
                            className="btn btn-danger"
                            style={{ padding: '3px 8px', fontSize: '0.75rem' }}
                            title="Delete this record from Database & Staging"
                          >
                            <Trash2 size={12} /> Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination bar */}
            {totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', flexWrap: 'wrap', gap: '10px' }}>
                <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                  Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, totalRecords)} of {totalRecords} records
                </span>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    className="btn btn-secondary"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    style={{ padding: '4px 10px', fontSize: '0.8rem' }}
                  >
                    Previous
                  </button>
                  <button
                    className="btn btn-secondary"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    style={{ padding: '4px 10px', fontSize: '0.8rem' }}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* VIEW 2: REGISTERED BATCHES TABLE */}
      {activeView === 'batches' && (
        <div className="gov-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
            <h2 style={{ fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: '8px', color: '#0f172a' }}>
              <FileText size={18} color="#1d4ed8" />
              Registered Batches ({batches.length})
            </h2>
            <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>
              Showing all active & SQL-synchronized batches
            </span>
          </div>

          {batches.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 20px', color: '#64748b', background: '#f8fafc', borderRadius: '4px', border: '1px dashed #cbd5e1' }}>
              <div style={{ width: '44px', height: '44px', borderRadius: '50%', background: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                <Layers size={22} color="#64748b" />
              </div>
              <p style={{ fontWeight: 700, color: '#1e293b', marginBottom: '4px' }}>No processing batches found</p>
              <p style={{ fontSize: '0.85rem', marginBottom: '16px' }}>Upload your first APBS fixed-width response file to start parsing.</p>
              <Link to="/batches/new" className="btn btn-primary">
                <PlusCircle size={15} /> Upload First Batch
              </Link>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Batch Identifier</th>
                    <th>Status</th>
                    <th>Files</th>
                    <th>Total Records</th>
                    <th>Valid / Invalid</th>
                    <th>DB Push Status</th>
                    <th>Created Date & Time</th>
                    <th style={{ textAlign: 'center' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map((batch) => (
                    <tr key={batch.batch_id}>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#0f172a' }}>
                          {batch.batch_id}
                        </span>
                      </td>
                      <td>
                        <StatusBadge status={batch.status} />
                      </td>
                      <td>
                        <strong>{batch.total_files}</strong> file{batch.total_files !== 1 ? 's' : ''}
                        {batch.duplicate_files > 0 && (
                          <span style={{ fontSize: '0.75rem', color: '#b45309', fontWeight: 600, marginLeft: '6px' }}>
                            ({batch.duplicate_files} dup)
                          </span>
                        )}
                      </td>
                      <td style={{ fontWeight: 600 }}>
                        {batch.total_records.toLocaleString()}
                      </td>
                      <td>
                        <span style={{ color: '#15803d', fontWeight: 700 }}>{batch.valid_records.toLocaleString()}</span>
                        <span style={{ color: '#94a3b8', margin: '0 4px' }}>/</span>
                        <span style={{ color: batch.invalid_records > 0 ? '#b91c1c' : '#64748b', fontWeight: batch.invalid_records > 0 ? 700 : 400 }}>
                          {batch.invalid_records.toLocaleString()}
                        </span>
                      </td>
                      <td>
                        {getDbPushBadge(batch)}
                      </td>
                      <td style={{ color: '#475569', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                        {new Date(batch.created_at).toLocaleString()}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <div style={{ display: 'inline-flex', gap: '5px', flexWrap: 'wrap', justifyContent: 'center' }}>
                          <button
                            onClick={() => { setSelectedBatch(batch.batch_id); setActiveView('records'); }}
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '0.75rem', borderColor: '#3b82f6', color: '#1d4ed8' }}
                            title="Inspect parsed records for this batch"
                          >
                            <Table size={12} /> Records
                          </button>
                          <Link 
                            to={`/logs?batch_id=${batch.batch_id}`} 
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                            title="View batch audit logs"
                          >
                            <Terminal size={12} /> Logs
                          </Link>
                          <Link 
                            to={`/batches/${batch.batch_id}/results`} 
                            className="btn btn-primary"
                            style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                            title="Verification & downloads"
                          >
                            Results <ArrowRight size={11} />
                          </Link>
                          <button
                            onClick={() => promptDeleteBatch(batch.batch_id)}
                            disabled={deletingId === batch.batch_id}
                            className="btn btn-danger"
                            style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                            title="Permanently delete batch and its database records"
                          >
                            <Trash2 size={12} /> Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Custom Application Confirmation Modal */}
      <Modal
        isOpen={modalConfig.isOpen}
        onClose={closeModal}
        onConfirm={modalConfig.onConfirm}
        title={modalConfig.title}
        description={modalConfig.description}
        confirmText={modalConfig.confirmText}
        variant={modalConfig.variant}
        details={modalConfig.details}
        loading={Boolean(deletingId)}
      />

      {/* Custom Application Toast Notification */}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
