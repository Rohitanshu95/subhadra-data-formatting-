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
  Trash2,
  AlertOctagon,
  User,
  Eye,
  FileWarning,
  Info,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Download
} from 'lucide-react';
import { listBatches, getOverviewStats, getParsedRecords, deleteBatch, deleteRecord, downloadRecordsAsCSV, downloadRecordsAsText, getActiveImports } from '../services/api';
import MetricCard from '../components/MetricCard';
import StatusBadge from '../components/StatusBadge';
import Modal from '../components/Modal';
import Toast from '../components/Toast';

export default function Dashboard() {
  const [activeView, setActiveView] = useState('records'); // 'records', 'batches', or 'errors'
  const [batches, setBatches] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeImports, setActiveImports] = useState({});
  const activeImportsRef = useRef({});

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
  const [errorTypeFilter, setErrorTypeFilter] = useState('ALL');

  // Multi-selection state for Registered Files batch delete
  const [selectedBatchIds, setSelectedBatchIds] = useState([]);

  // Inspected raw error record modal state
  const [inspectedRecord, setInspectedRecord] = useState(null);

  // Manual refresh spinner and success animation states
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshSuccess, setRefreshSuccess] = useState(false);

  // Client-side in-memory session caches to eliminate redundant DB/network calls on tab switches
  const recordsCacheRef = useRef({});
  const overviewCacheRef = useRef(null);

  // Debounce search input for instant dynamic filtering
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Polling for active background database imports with adaptive intervals & error backoff
  useEffect(() => {
    let isMounted = true;
    let timerId = null;

    const pollActiveImports = async () => {
      let nextDelay = 5000; // default idle check interval
      try {
        const active = await getActiveImports();
        if (!isMounted) return;

        const prevKeys = Object.keys(activeImportsRef.current || {});
        const newKeys = Object.keys(active || {});

        // If an active import completed, automatically refresh dashboard stats & batches
        if (prevKeys.length > 0 && newKeys.length < prevKeys.length) {
          fetchOverviewData(true);
          setToast({ message: 'Database import completed! Pipeline statistics updated.', type: 'success' });
          setTimeout(() => setToast(null), 4000);
        }

        activeImportsRef.current = active || {};
        setActiveImports(active || {});

        // If there are active imports running, poll faster (1.5s) for smooth real-time telemetry
        if (newKeys.length > 0) {
          nextDelay = 1500;
        }
      } catch (err) {
        // Backend offline or error: back off to 8s to prevent console spam
        nextDelay = 8000;
      } finally {
        if (isMounted) {
          timerId = setTimeout(pollActiveImports, nextDelay);
        }
      }
    };

    pollActiveImports();
    return () => {
      isMounted = false;
      if (timerId) clearTimeout(timerId);
    };
  }, []);

  // Fetch overview stats and batch list (cached per session unless forced)
  const fetchOverviewData = async (forceRefresh = false) => {
    if (!forceRefresh && overviewCacheRef.current) {
      setBatches(overviewCacheRef.current.batches || []);
      setStats(overviewCacheRef.current.stats || null);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const [batchesData, statsData] = await Promise.all([
        listBatches(forceRefresh),
        getOverviewStats(forceRefresh).catch(() => null),
      ]);
      const batchesList = batchesData || [];
      overviewCacheRef.current = { batches: batchesList, stats: statsData };
      setBatches(batchesList);
      setStats(statsData);
    } catch (err) {
      console.error("Failed to load overview data", err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch parsed records dynamically with client-side caching per tab/view
  const fetchRecordsData = useCallback(async (forceRefresh = false) => {
    // Registered Files tab doesn't need parsed record streams
    if (activeView === 'batches') {
      return;
    }

    const cacheKey = JSON.stringify({
      activeView,
      selectedBatch,
      page,
      pageSize,
      successFlag: activeView === 'records' ? successFlag : '',
      reasonCode: activeView === 'records' ? reasonCode.trim() : '',
      statusFilter: activeView === 'records' ? statusFilter : '',
      errorTypeFilter: activeView === 'errors' ? errorTypeFilter : '',
      search: debouncedSearch.trim(),
    });

    if (!forceRefresh && recordsCacheRef.current[cacheKey]) {
      const cached = recordsCacheRef.current[cacheKey];
      setRecords(cached.records || []);
      setTotalRecords(cached.total || 0);
      setTotalPages(cached.total_pages || 1);
      setDataSource(cached.data_source || 'Production Database & Staging');
      setRecordsLoading(false);
      return;
    }

    try {
      setRecordsLoading(true);
      const params = {
        page,
        page_size: pageSize,
      };

      if (activeView === 'errors') {
        params.status = 'Invalid';
        if (errorTypeFilter !== 'ALL') {
          params.reason_code = errorTypeFilter;
        }
      } else {
        if (successFlag !== '') params.success_flag = successFlag;
        if (reasonCode.trim() !== '') params.reason_code = reasonCode.trim();
        if (statusFilter !== 'ALL') params.status = statusFilter;
      }

      if (debouncedSearch.trim() !== '') params.search = debouncedSearch.trim();
      if (forceRefresh) params.refresh = true;

      const batchTarget = selectedBatch && selectedBatch !== 'ALL' ? selectedBatch : 'all';
      const data = await getParsedRecords(batchTarget, params);
      recordsCacheRef.current[cacheKey] = data;
      setRecords(data.records || []);
      setTotalRecords(data.total || 0);
      setTotalPages(data.total_pages || 1);
      setDataSource(data.data_source || 'Production Database & Staging');
    } catch (err) {
      console.error("Failed to load parsed records", err);
    } finally {
      setRecordsLoading(false);
    }
  }, [activeView, selectedBatch, page, pageSize, successFlag, reasonCode, statusFilter, errorTypeFilter, debouncedSearch]);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    setRefreshSuccess(false);
    recordsCacheRef.current = {};
    overviewCacheRef.current = null;
    try {
      await Promise.all([
        fetchOverviewData(true),
        activeView !== 'batches' ? fetchRecordsData(true) : Promise.resolve(),
      ]);
      setRefreshSuccess(true);
      showToast('Dashboard data refreshed successfully.');
      setTimeout(() => {
        setRefreshSuccess(false);
      }, 3000);
    } catch (err) {
      showToast('Failed to refresh data.', 'error');
    } finally {
      setIsRefreshing(false);
    }
  };

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
    setErrorTypeFilter('ALL');
    setSearchQuery('');
    setDebouncedSearch('');
    setPage(1);
  };

  const handleDownloadRecords = async (format, downloadAll = true) => {
    try {
      const params = {};
      let batchTarget = 'all';

      if (!downloadAll) {
        if (selectedBatch && selectedBatch !== 'ALL') {
          params.batch_id = selectedBatch;
          batchTarget = selectedBatch;
        }
        if (successFlag !== '') params.success_flag = successFlag;
        if (reasonCode.trim() !== '') params.reason_code = reasonCode.trim();
        if (statusFilter !== 'ALL') params.status = statusFilter;
        if (debouncedSearch.trim() !== '') params.search = debouncedSearch.trim();
      }

      if (format === 'csv') {
        await downloadRecordsAsCSV(batchTarget, params);
        showToast(downloadAll ? 'Downloading ALL records from complete database (CSV)...' : `Streaming ${batchTarget} CSV download...`);
      } else if (format === 'text') {
        await downloadRecordsAsText(batchTarget, params);
        showToast(downloadAll ? 'Downloading ALL records from complete database (Text)...' : `Streaming ${batchTarget} Text download...`);
      }
    } catch (err) {
      console.error(`Failed to download ${format}:`, err);
      showToast(`Failed to download records as ${format.toUpperCase()}`, 'error');
    }
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
          setSelectedBatchIds(prev => prev.filter(id => id !== batchId));
          recordsCacheRef.current = {};
          overviewCacheRef.current = null;
          closeModal();
          await Promise.all([fetchOverviewData(true), fetchRecordsData(true)]);
        } catch (err) {
          showToast(`Failed to delete batch: ${err.response?.data?.detail || err.message}`, 'error');
        } finally {
          setDeletingId(null);
        }
      }
    });
  };

  // Batch multi-selection handlers
  const handleToggleSelectBatch = (batchId) => {
    setSelectedBatchIds(prev =>
      prev.includes(batchId) ? prev.filter(id => id !== batchId) : [...prev, batchId]
    );
  };

  const handleSelectAllBatches = (e) => {
    if (e.target.checked) {
      setSelectedBatchIds(batches.map(b => b.batch_id));
    } else {
      setSelectedBatchIds([]);
    }
  };

  // Bulk batch deletion handler with custom Modal
  const promptDeleteSelectedBatches = () => {
    if (selectedBatchIds.length === 0) return;

    const count = selectedBatchIds.length;
    const selectedBatchesInfo = batches.filter(b => selectedBatchIds.includes(b.batch_id));
    const totalAffectedRecords = selectedBatchesInfo.reduce((acc, b) => acc + (b.total_records || 0), 0);

    setModalConfig({
      isOpen: true,
      title: `Delete ${count} Selected Registered File${count !== 1 ? 's' : ''}`,
      description: `Are you sure you want to permanently delete the ${count} selected registered file(s)? All corresponding database transactions, audit logs, and storage artifacts will be removed.`,
      confirmText: `Delete ${count} File${count !== 1 ? 's' : ''}`,
      variant: 'danger',
      details: (
        <div>
          <div style={{ marginBottom: '8px', maxHeight: '140px', overflowY: 'auto', background: '#ffffff', padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px' }}>
            {selectedBatchesInfo.map(b => (
              <div key={b.batch_id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', padding: '3px 0', borderBottom: '1px solid #f1f5f9' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#0f172a' }}>{b.batch_id}</span>
                <span style={{ color: '#64748b' }}>{b.total_records?.toLocaleString() || 0} records</span>
              </div>
            ))}
          </div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#0f172a', marginBottom: '6px' }}>
            Total Records Affected: <span style={{ color: '#dc2626' }}>{totalAffectedRecords.toLocaleString()}</span>
          </div>
          <div style={{ color: '#b91c1c', fontSize: '0.8rem' }}>
            ⚠️ This action is permanent and cannot be undone.
          </div>
        </div>
      ),
      onConfirm: async () => {
        try {
          setDeletingId('BULK_BATCH_DELETE');
          const results = await Promise.allSettled(selectedBatchIds.map(id => deleteBatch(id)));
          const successCount = results.filter(r => r.status === 'fulfilled').length;
          const failedCount = results.filter(r => r.status === 'rejected').length;

          if (failedCount === 0) {
            showToast(`Successfully deleted ${successCount} file(s) and their database records.`);
          } else {
            showToast(`Deleted ${successCount} file(s), ${failedCount} failed.`, 'warning');
          }

          setSelectedBatchIds([]);
          recordsCacheRef.current = {};
          overviewCacheRef.current = null;
          closeModal();
          await Promise.all([fetchOverviewData(true), fetchRecordsData(true)]);
        } catch (err) {
          showToast(`Error during bulk deletion: ${err.message}`, 'error');
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
          recordsCacheRef.current = {};
          overviewCacheRef.current = null;
          closeModal();
          await Promise.all([fetchOverviewData(true), fetchRecordsData(true)]);
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
    const activeProg = activeImports[batch.batch_id];

    if (status === 'IMPORTING' || activeProg) {
      const pct = activeProg ? activeProg.percent : 0;
      const pushed = activeProg ? activeProg.total_imported : 0;
      const exp = activeProg ? (activeProg.total_expected_records || batch.valid_records) : batch.valid_records;
      const eta = activeProg ? activeProg.eta_formatted : 'calculating...';
      return (
        <div style={{ minWidth: '150px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', marginBottom: '3px' }}>
            <span style={{ fontWeight: 700, color: '#1d4ed8' }}>
              {pct}% Pushed
            </span>
            <span style={{ color: '#64748b', fontSize: '0.7rem' }}>
              ~{eta}
            </span>
          </div>
          <div style={{ width: '100%', height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{
              width: `${Math.max(3, pct)}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #2563eb, #10b981)',
              borderRadius: '3px',
              transition: 'width 0.3s ease-out'
            }} />
          </div>
          <div style={{ fontSize: '0.68rem', color: '#475569', marginTop: '3px' }}>
            {pushed.toLocaleString()} / {exp.toLocaleString()} rec
          </div>
        </div>
      );
    }

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

  const renderPagination = (recordLabel = 'records') => {
    if (totalRecords === 0) return null;

    const startItem = (page - 1) * pageSize + 1;
    const endItem = Math.min(page * pageSize, totalRecords);

    // Generate visible page numbers (max 5 around current page)
    const pageNumbers = [];
    const maxVisible = 5;
    let startPage = Math.max(1, page - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    if (endPage - startPage + 1 < maxVisible) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }
    for (let i = startPage; i <= endPage; i++) {
      pageNumbers.push(i);
    }

    return (
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginTop: '16px',
        paddingTop: '14px',
        borderTop: '1px solid #e2e8f0',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', color: '#64748b' }}>
          <span>
            Showing <strong style={{ color: '#0f172a' }}>{startItem.toLocaleString()}</strong> to <strong style={{ color: '#0f172a' }}>{endItem.toLocaleString()}</strong> of <strong style={{ color: '#0f172a' }}>{totalRecords.toLocaleString()}</strong> {recordLabel}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: '8px' }}>
            <span style={{ fontSize: '0.8rem' }}>Rows per page:</span>
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
              style={{ padding: '3px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.8rem', backgroundColor: '#ffffff' }}
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={250}>250</option>
              <option value={500}>500</option>
              <option value={1000}>All (1000)</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button
            className="btn btn-secondary"
            disabled={page <= 1}
            onClick={() => setPage(1)}
            style={{ padding: '5px 8px', fontSize: '0.8rem' }}
            title="First Page"
          >
            <ChevronsLeft size={14} />
          </button>

          <button
            className="btn btn-secondary"
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            style={{ padding: '5px 8px', fontSize: '0.8rem' }}
            title="Previous Page"
          >
            <ChevronLeft size={14} />
          </button>

          {startPage > 1 && (
            <>
              <button
                className="btn btn-secondary"
                onClick={() => setPage(1)}
                style={{ padding: '4px 9px', fontSize: '0.8rem' }}
              >
                1
              </button>
              {startPage > 2 && <span style={{ padding: '0 4px', color: '#94a3b8' }}>...</span>}
            </>
          )}

          {pageNumbers.map(pageNum => (
            <button
              key={pageNum}
              onClick={() => setPage(pageNum)}
              style={{
                padding: '4px 10px',
                fontSize: '0.8rem',
                fontWeight: pageNum === page ? 700 : 500,
                borderRadius: '4px',
                border: pageNum === page ? '1px solid #2563eb' : '1px solid #cbd5e1',
                backgroundColor: pageNum === page ? '#2563eb' : '#ffffff',
                color: pageNum === page ? '#ffffff' : '#334155',
                cursor: 'pointer',
              }}
            >
              {pageNum}
            </button>
          ))}

          {endPage < totalPages && (
            <>
              {endPage < totalPages - 1 && <span style={{ padding: '0 4px', color: '#94a3b8' }}>...</span>}
              <button
                className="btn btn-secondary"
                onClick={() => setPage(totalPages)}
                style={{ padding: '4px 9px', fontSize: '0.8rem' }}
              >
                {totalPages}
              </button>
            </>
          )}

          <button
            className="btn btn-secondary"
            disabled={page >= totalPages}
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            style={{ padding: '5px 8px', fontSize: '0.8rem' }}
            title="Next Page"
          >
            <ChevronRight size={14} />
          </button>

          <button
            className="btn btn-secondary"
            disabled={page >= totalPages}
            onClick={() => setPage(totalPages)}
            style={{ padding: '5px 8px', fontSize: '0.8rem' }}
            title="Last Page"
          >
            <ChevronsRight size={14} />
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="app-container">
      {/* Header section */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '14px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', color: '#0f172a', marginBottom: '4px' }}>
            APBS Processing Dashboard
          </h1>
          <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
            Aadhaar Payment Bridge System — 177-Character Fixed-Width Validation & DB Lifecycle Pipeline
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button 
            onClick={handleManualRefresh} 
            disabled={isRefreshing || loading || recordsLoading}
            className={`btn ${refreshSuccess ? 'btn-success' : 'btn-secondary'}`}
            style={{
              transition: 'all 0.25s ease',
              backgroundColor: refreshSuccess ? '#dcfce7' : '',
              color: refreshSuccess ? '#15803d' : '',
              borderColor: refreshSuccess ? '#86efac' : '',
            }}
            title="Refresh dashboard data from database"
          >
            {refreshSuccess ? (
              <>
                <CheckCircle2 size={15} color="#15803d" />
                <span>Refreshed!</span>
              </>
            ) : (
              <>
                <RefreshCw 
                  size={15} 
                  className={isRefreshing || loading || recordsLoading ? 'animate-spin' : ''} 
                />
                <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
              </>
            )}
          </button>
          <Link to="/batches/new" className="btn btn-primary">
            <PlusCircle size={15} />
            Upload New File
          </Link>
        </div>
      </div>

      {/* Live Active Database Ingestion Banner */}
      {Object.keys(activeImports).length > 0 && (
        <div style={{
          marginBottom: '22px',
          background: 'linear-gradient(135deg, #eff6ff 0%, #ffffff 100%)',
          border: '1px solid #bfdbfe',
          borderLeft: '5px solid #2563eb',
          borderRadius: '8px',
          padding: '16px 20px',
          boxShadow: '0 4px 15px -3px rgba(37, 99, 235, 0.12)',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}>
          {Object.entries(activeImports).map(([bId, prog]) => (
            <div key={bId} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{
                    width: '34px',
                    height: '34px',
                    borderRadius: '8px',
                    background: '#dbeafe',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    border: '1px solid #93c5fd',
                  }}>
                    <Database size={17} color="#1d4ed8" className="animate-pulse" />
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 700, color: '#0f172a', fontSize: '0.96rem' }}>
                        Active Database Import in Progress
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', background: '#e2e8f0', padding: '2px 7px', borderRadius: '4px', color: '#1e293b' }}>
                        {bId}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '2px' }}>
                      Pushed: <strong style={{ color: '#1d4ed8' }}>{prog.data_pushed_mb || 0} MB</strong> ({prog.total_imported?.toLocaleString() || 0} rec) • Remaining: <strong style={{ color: '#047857' }}>{prog.data_remaining_mb ?? '0.0'} MB</strong> ({prog.remaining_records?.toLocaleString() ?? 0} rec) • Files: {prog.file_idx}/{prog.total_files}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#1d4ed8', fontFamily: 'var(--font-mono)' }}>
                      {prog.percent}% • ETA: ~{prog.eta_formatted || 'calculating...'}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                      {prog.speed_records_sec?.toLocaleString() || 0} rec/sec
                    </div>
                  </div>
                  <Link
                    to={`/batches/${bId}/results`}
                    className="btn btn-secondary"
                    style={{ padding: '5px 12px', fontSize: '0.78rem', borderColor: '#bfdbfe', color: '#1d4ed8', background: '#ffffff', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                  >
                    View Live Monitor <ArrowRight size={13} />
                  </Link>
                </div>
              </div>

              {/* Progress bar */}
              <div style={{ width: '100%', height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{
                  width: `${Math.max(2, prog.percent)}%`,
                  height: '100%',
                  background: 'linear-gradient(90deg, #2563eb 0%, #3b82f6 60%, #10b981 100%)',
                  borderRadius: '4px',
                  transition: 'width 0.3s ease-out',
                }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 5 Pipeline-Stage Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '14px', marginBottom: '24px' }}>
        <MetricCard 
          title="Total Records Parsed" 
          value={totalParsed.toLocaleString()} 
          subtitle="Processed across all batches" 
          icon={Layers} 
          color="#1d4ed8" 
          onClick={() => { setActiveView('records'); setStatusFilter('ALL'); setPage(1); }}
        />
        <MetricCard 
          title="Awaiting Verification" 
          value={awaitingVerification.toLocaleString()} 
          subtitle="Processed, pending review" 
          icon={Clock} 
          color="#7e22ce" 
          onClick={() => { setActiveView('records'); setStatusFilter('Pending Verification'); setPage(1); }}
        />
        <MetricCard 
          title="Committed to DB" 
          value={committedToDb.toLocaleString()} 
          subtitle="Unique records inserted in SQL" 
          icon={Database} 
          color="#15803d" 
          onClick={() => { setActiveView('records'); setStatusFilter('Committed'); setPage(1); }}
        />
        <MetricCard 
          title="Duplicates Skipped" 
          value={duplicatesSkipped.toLocaleString()} 
          subtitle="File & record duplicate collisions" 
          icon={CopyCheck} 
          color="#b45309" 
          onClick={() => { setActiveView('records'); setStatusFilter('Duplicate'); setPage(1); }}
        />
        <MetricCard 
          title="Failed / Invalid Records" 
          value={failedRecords.toLocaleString()} 
          subtitle="Schema & length violations (Click to inspect)" 
          icon={AlertTriangle} 
          color="#b91c1c" 
          onClick={() => { setActiveView('errors'); setErrorTypeFilter('ALL'); setPage(1); }}
        />
      </div>

      {/* Main View Mode Selector Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', gap: '6px', background: '#e2e8f0', padding: '4px', borderRadius: '6px', flexWrap: 'wrap' }}>
          <button
            onClick={() => { setActiveView('records'); setPage(1); }}
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
            Parsed APBS Records {activeView === 'records' && `(${totalRecords.toLocaleString()})`}
          </button>

          <button
            onClick={() => { setActiveView('errors'); setPage(1); }}
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
              background: activeView === 'errors' ? '#ffffff' : 'transparent',
              color: activeView === 'errors' ? '#b91c1c' : failedRecords > 0 ? '#b91c1c' : '#64748b',
              boxShadow: activeView === 'errors' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
            }}
          >
            <AlertTriangle size={15} color={activeView === 'errors' || failedRecords > 0 ? '#b91c1c' : '#64748b'} />
            Error & Invalid Records Log
            {failedRecords > 0 && (
              <span style={{
                background: activeView === 'errors' ? '#fee2e2' : '#fecaca',
                color: '#b91c1c',
                padding: '1px 6px',
                borderRadius: '10px',
                fontSize: '0.75rem',
                fontWeight: 800,
              }}>
                {failedRecords.toLocaleString()}
              </span>
            )}
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
            Registered Files ({batches.length})
          </button>
        </div>

        {activeView === 'records' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#166534', background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '4px 10px', borderRadius: '4px' }}>
            <CheckCircle2 size={15} color="#16a34a" />
            <span style={{ fontWeight: 600 }}>Full Unmasked Data View Active</span>
          </div>
        )}

        {activeView === 'errors' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#991b1b', background: '#fef2f2', border: '1px solid #fecaca', padding: '4px 10px', borderRadius: '4px' }}>
            <AlertOctagon size={15} color="#dc2626" />
            <span style={{ fontWeight: 600 }}>Validation & Length Error Diagnostics Log</span>
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
                  Filter by File
                </label>
                <select
                  value={selectedBatch}
                  onChange={(e) => { setSelectedBatch(e.target.value); setPage(1); }}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.875rem', backgroundColor: '#ffffff' }}
                >
                  <option value="ALL">All Registered Files</option>
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
                  <option value="Invalid">Invalid (Error Records)</option>
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

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.85rem', color: '#64748b', flexWrap: 'wrap' }}>
                {/* Download Options */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <button
                    onClick={() => handleDownloadRecords('csv', true)}
                    disabled={committedToDb === 0 && totalRecords === 0}
                    className="btn btn-secondary"
                    style={{ 
                      padding: '6px 12px', 
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      backgroundColor: '#fef3c7',
                      borderColor: '#f59e0b',
                      color: '#92400e',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                    title="Download ALL records present in the database as CSV"
                  >
                    <Download size={14} />
                    CSV (All Records)
                  </button>
                  <button
                    onClick={() => handleDownloadRecords('text', true)}
                    disabled={committedToDb === 0 && totalRecords === 0}
                    className="btn btn-secondary"
                    style={{ 
                      padding: '6px 12px', 
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      backgroundColor: '#dbeafe',
                      borderColor: '#3b82f6',
                      color: '#1e40af',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                    title="Download ALL records present in the database as pipe-delimited text"
                  >
                    <Download size={14} />
                    Text (All Records)
                  </button>

                  {hasActiveFilters && (
                    <>
                      <button
                        onClick={() => handleDownloadRecords('csv', false)}
                        disabled={totalRecords === 0}
                        className="btn btn-secondary"
                        style={{ 
                          padding: '6px 10px', 
                          fontSize: '0.75rem',
                          fontWeight: 500,
                          backgroundColor: '#f8fafc',
                          borderColor: '#cbd5e1',
                          color: '#475569',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                        title={`Download only the ${totalRecords.toLocaleString()} filtered records as CSV`}
                      >
                        <Download size={12} />
                        CSV (Filtered)
                      </button>
                      <button
                        onClick={() => handleDownloadRecords('text', false)}
                        disabled={totalRecords === 0}
                        className="btn btn-secondary"
                        style={{ 
                          padding: '6px 10px', 
                          fontSize: '0.75rem',
                          fontWeight: 500,
                          backgroundColor: '#f8fafc',
                          borderColor: '#cbd5e1',
                          color: '#475569',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                        title={`Download only the ${totalRecords.toLocaleString()} filtered records as Text`}
                      >
                        <Download size={12} />
                        Text (Filtered)
                      </button>
                    </>
                  )}
                </div>

                {/* Divider */}
                <div style={{ width: '1px', height: '24px', backgroundColor: '#cbd5e1' }} />

                {/* Pagination and Page Size */}
                <span>Page {page} of {totalPages} ({totalRecords.toLocaleString()} total)</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                  style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.8rem', backgroundColor: '#ffffff' }}
                >
                  <option value={10}>10 / page</option>
                  <option value={25}>25 / page</option>
                  <option value={50}>50 / page</option>
                  <option value={100}>100 / page</option>
                  <option value={250}>250 / page</option>
                  <option value={500}>500 / page</option>
                  <option value={1000}>All (1000) / page</option>
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
                      <th style={{ whiteSpace: 'nowrap', textAlign: 'center' }}>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((r, idx) => {
                      const isInvalid = r.status === 'Invalid';
                      return (
                        <tr key={idx} style={{ backgroundColor: isInvalid ? '#fff5f5' : 'inherit' }}>
                          <td style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{(page - 1) * pageSize + idx + 1}</td>
                          <td><span className={isInvalid ? "badge badge-failed" : "badge badge-ready"}>{r.apbs_transaction_code || (isInvalid ? 'ERR' : '—')}</span></td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>{r.destination_bank_iin || '—'}</td>
                          <td>{r.destination_account_type || '—'}</td>
                          <td>{r.ledger_folio_number || '—'}</td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: isInvalid ? '#b91c1c' : '#1e293b' }}>
                            {r.beneficiary_aadhaar_number || '—'}
                          </td>
                          <td style={{ fontWeight: 600, color: isInvalid ? '#b91c1c' : '#0f172a', minWidth: '130px' }}>
                            {isInvalid && <AlertTriangle size={12} color="#b91c1c" style={{ display: 'inline', marginRight: '4px' }} />}
                            {r.beneficiary_name || '—'}
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>{r.sponsor_bank_iin || '—'}</td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>{r.user_number || '—'}</td>
                          <td style={{ fontSize: '0.8rem', color: '#475569' }}>{r.user_name_narration || '—'}</td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{r.user_credit_reference || '—'}</td>
                          <td style={{ fontWeight: 700, color: isInvalid ? '#b91c1c' : '#15803d' }}>{r.amount || '—'}</td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>{r.item_sequence_number || '—'}</td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{r.checksum || '—'}</td>
                          <td>
                            {r.success_flag === '1' || r.success_flag?.startsWith('1') ? (
                              <span style={{ color: '#15803d', fontWeight: 700 }}>1 (Credited)</span>
                            ) : r.success_flag === '0' || r.success_flag?.startsWith('0') ? (
                              <span style={{ color: '#b91c1c', fontWeight: 700 }}>0 (Returned)</span>
                            ) : isInvalid ? (
                              <span style={{ color: '#b91c1c', fontWeight: 700 }}>Failed</span>
                            ) : (
                              r.success_flag || '—'
                            )}
                          </td>
                          <td style={{ color: '#94a3b8' }}>{r.filler || '—'}</td>
                          <td style={{ color: isInvalid ? '#b91c1c' : 'inherit' }}>
                            <strong>{r.reason_code || (isInvalid ? r.error_type : '—')}</strong>
                            {isInvalid && r.error_detail && (
                              <div style={{ fontSize: '0.7rem', color: '#dc2626' }}>{r.error_detail}</div>
                            )}
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)', color: '#334155' }}>
                            {r.destination_bank_account_number || '—'}
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <div style={{ display: 'inline-flex', gap: '4px' }}>
                              {isInvalid && (
                                <button
                                  onClick={() => setInspectedRecord(r)}
                                  className="btn btn-secondary"
                                  style={{ padding: '3px 8px', fontSize: '0.75rem', borderColor: '#fca5a5', color: '#b91c1c' }}
                                  title="Inspect full raw error data"
                                >
                                  <Eye size={12} /> Inspect
                                </button>
                              )}
                              <button
                                onClick={() => promptDeleteRecord(r)}
                                disabled={deletingId === (r.id || r.user_credit_reference)}
                                className="btn btn-danger"
                                style={{ padding: '3px 8px', fontSize: '0.75rem' }}
                                title="Delete this record from Database & Staging"
                              >
                                <Trash2 size={12} /> Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination bar */}
            {renderPagination('clean records')}
          </div>
        </>
      )}

      {/* VIEW 2: ERROR & INVALID RECORDS LOG VIEW */}
      {activeView === 'errors' && (
        <>
          {/* Dynamic Error Filters Card */}
          <div className="gov-card" style={{ padding: '16px', marginBottom: '18px', borderLeft: '4px solid #b91c1c' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', alignItems: 'end' }}>
              {/* Batch Filter Dropdown */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                  Filter by File
                </label>
                <select
                  value={selectedBatch}
                  onChange={(e) => { setSelectedBatch(e.target.value); setPage(1); }}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.875rem', backgroundColor: '#ffffff' }}
                >
                  <option value="ALL">All Registered Files</option>
                  {batches.map((b) => (
                    <option key={b.batch_id} value={b.batch_id}>
                      {b.batch_id} ({b.invalid_records} errors)
                    </option>
                  ))}
                </select>
              </div>

              {/* Error Classification Filter */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                  Error Classification
                </label>
                <select
                  value={errorTypeFilter}
                  onChange={(e) => { setErrorTypeFilter(e.target.value); setPage(1); }}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.875rem', backgroundColor: '#ffffff' }}
                >
                  <option value="ALL">All Error Classifications</option>
                  <option value="INVALID_RECORD_LENGTH">INVALID_RECORD_LENGTH (Length ≠ 177)</option>
                  <option value="INVALID_CHECKSUM">INVALID_CHECKSUM (Mod 11 Failed)</option>
                  <option value="REQUIRED_FIELD_MISSING">REQUIRED_FIELD_MISSING</option>
                  <option value="INVALID_NUMERIC">INVALID_NUMERIC (Non-numeric digits)</option>
                  <option value="INVALID_TRANSACTION_CODE">INVALID_TRANSACTION_CODE</option>
                </select>
              </div>

              {/* Search Query for Beneficiary / Aadhaar / Error Details */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
                  Search by Beneficiary / Aadhaar / Ref / Reason
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="text"
                    placeholder="Search error logs..."
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
                  style={{ width: '100%', padding: '8px 14px' }}
                >
                  Clear Filters
                </button>
              </div>
            </div>

            <div style={{ marginTop: '12px', fontSize: '0.825rem', color: '#b91c1c', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Info size={14} />
              <span>Showing invalid records with extracted <strong>Beneficiary Name</strong>, <strong>Aadhaar Number</strong>, line numbers, and error root-cause diagnostics.</span>
            </div>
          </div>

          {/* Error Records Table Card */}
          <div className="gov-card" style={{ padding: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={18} color="#b91c1c" />
                <h2 style={{ fontSize: '1.1rem', color: '#0f172a' }}>
                  Invalid APBS Records Log
                </h2>
                <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>
                  — Parsed failure diagnostics with complete user identification
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: '#64748b' }}>
                <span>Page {page} of {totalPages} ({totalRecords.toLocaleString()} errors)</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                  style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.8rem', backgroundColor: '#ffffff' }}
                >
                  <option value={10}>10 / page</option>
                  <option value={25}>25 / page</option>
                  <option value={50}>50 / page</option>
                  <option value={100}>100 / page</option>
                  <option value={250}>250 / page</option>
                  <option value={500}>500 / page</option>
                  <option value={1000}>All (1000) / page</option>
                </select>
              </div>
            </div>

            {records.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px 20px', color: '#15803d', background: '#f0fdf4', borderRadius: '4px', border: '1px solid #bbf7d0' }}>
                <CheckCircle2 size={36} color="#15803d" style={{ margin: '0 auto 8px' }} />
                <p style={{ fontWeight: 700, fontSize: '1.05rem', color: '#15803d' }}>No invalid records found</p>
                <p style={{ fontSize: '0.85rem', color: '#166534' }}>
                  {hasActiveFilters ? 'No error records matched the active filters.' : 'All parsed records in the system are valid and clean!'}
                </p>
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
                      <th style={{ whiteSpace: 'nowrap' }}>LINE #</th>
                      <th style={{ whiteSpace: 'nowrap' }}>BENEFICIARY / USER IDENTITY</th>
                      <th style={{ whiteSpace: 'nowrap' }}>AADHAAR NUMBER</th>
                      <th style={{ whiteSpace: 'nowrap' }}>CREDIT REF</th>
                      <th style={{ whiteSpace: 'nowrap' }}>AMOUNT (PAISE)</th>
                      <th style={{ whiteSpace: 'nowrap' }}>ERROR CLASSIFICATION</th>
                      <th style={{ whiteSpace: 'nowrap' }}>DIAGNOSTIC FAILURE REASON</th>
                      <th style={{ whiteSpace: 'nowrap' }}>SOURCE FILE</th>
                      <th style={{ whiteSpace: 'nowrap', textAlign: 'center' }}>ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((r, idx) => (
                      <tr key={idx} style={{ backgroundColor: '#fff8f8' }}>
                        <td style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{(page - 1) * pageSize + idx + 1}</td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#0f172a' }}>
                          {r.line_no ? `Line ${r.line_no}` : '—'}
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <div style={{ width: '22px', height: '22px', borderRadius: '50%', background: '#fee2e2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              <User size={12} color="#b91c1c" />
                            </div>
                            <div>
                              <div style={{ fontWeight: 700, color: '#0f172a' }}>
                                {r.beneficiary_name || 'Unidentified Beneficiary'}
                              </div>
                              {r.destination_bank_account_number && (
                                <div style={{ fontSize: '0.75rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
                                  A/C: {r.destination_bank_account_number} {r.destination_bank_iin ? `(${r.destination_bank_iin})` : ''}
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#b91c1c' }}>
                          {r.beneficiary_aadhaar_number || '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                          {r.user_credit_reference || '—'}
                        </td>
                        <td style={{ fontWeight: 700, color: '#475569' }}>
                          {r.amount || '—'}
                        </td>
                        <td>
                          <span className="badge badge-failed" style={{ fontSize: '0.75rem' }}>
                            {r.error_type || r.reason_code || 'INVALID_RECORD'}
                          </span>
                        </td>
                        <td style={{ color: '#b91c1c', fontWeight: 600, fontSize: '0.825rem', maxWidth: '280px' }}>
                          {r.error_detail || r.reason_code || 'Validation check failure'}
                        </td>
                        <td style={{ fontSize: '0.75rem', color: '#64748b' }}>
                          {r._source_file || r.batch_id || '—'}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <div style={{ display: 'inline-flex', gap: '4px' }}>
                            <button
                              onClick={() => setInspectedRecord(r)}
                              className="btn btn-secondary"
                              style={{ padding: '3px 8px', fontSize: '0.75rem', borderColor: '#fca5a5', color: '#b91c1c', background: '#ffffff' }}
                              title="Inspect raw character breakdown and error analysis"
                            >
                              <Eye size={12} /> Inspect
                            </button>
                            <button
                              onClick={() => promptDeleteRecord(r)}
                              disabled={deletingId === (r.id || r.user_credit_reference)}
                              className="btn btn-danger"
                              style={{ padding: '3px 8px', fontSize: '0.75rem' }}
                              title="Delete this record"
                            >
                              <Trash2 size={12} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination bar */}
            {renderPagination('error records')}
          </div>
        </>
      )}

      {/* VIEW 3: REGISTERED FILES TABLE */}
      {activeView === 'batches' && (
        <div className="gov-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
            <h2 style={{ fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: '8px', color: '#0f172a' }}>
              <FileText size={18} color="#1d4ed8" />
              Registered Files ({batches.length})
            </h2>
            <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>
              Showing all active & SQL-synchronized files
            </span>
          </div>

          {/* Multi-Selection Action Toolbar */}
          {selectedBatchIds.length > 0 && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              marginBottom: '14px',
              backgroundColor: '#eff6ff',
              border: '1px solid #bfdbfe',
              borderRadius: '6px',
              animation: 'fadeIn 0.15s ease-out'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#1d4ed8' }}>
                  {selectedBatchIds.length} of {batches.length} file{batches.length !== 1 ? 's' : ''} selected
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedBatchIds([])}
                  className="btn btn-secondary"
                  style={{ padding: '3px 10px', fontSize: '0.75rem' }}
                >
                  Clear Selection
                </button>
              </div>
              <button
                type="button"
                onClick={promptDeleteSelectedBatches}
                disabled={deletingId === 'BULK_BATCH_DELETE'}
                className="btn btn-danger"
                style={{ padding: '6px 14px', fontSize: '0.825rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                <Trash2 size={14} /> Delete Selected ({selectedBatchIds.length})
              </button>
            </div>
          )}

          {batches.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 20px', color: '#64748b', background: '#f8fafc', borderRadius: '4px', border: '1px dashed #cbd5e1' }}>
              <div style={{ width: '44px', height: '44px', borderRadius: '50%', background: '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                <Layers size={22} color="#64748b" />
              </div>
              <p style={{ fontWeight: 700, color: '#1e293b', marginBottom: '4px' }}>No processing files found</p>
              <p style={{ fontSize: '0.85rem', marginBottom: '16px' }}>Upload your first APBS fixed-width response file to start parsing.</p>
              <Link to="/batches/new" className="btn btn-primary">
                <PlusCircle size={15} /> Upload First File
              </Link>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: '40px', textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={batches.length > 0 && selectedBatchIds.length === batches.length}
                        onChange={handleSelectAllBatches}
                        title={selectedBatchIds.length === batches.length ? "Deselect all files" : "Select all files"}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                    </th>
                    <th>File Identifier</th>
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
                  {batches.map((batch) => {
                    const isSelected = selectedBatchIds.includes(batch.batch_id);
                    return (
                      <tr key={batch.batch_id} style={{ backgroundColor: isSelected ? '#eff6ff' : 'inherit' }}>
                        <td style={{ textAlign: 'center' }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleSelectBatch(batch.batch_id)}
                            style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                          />
                        </td>
                        <td>
                          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#0f172a' }}>
                            {batch.batch_id}
                          </span>
                        </td>
                        <td>
                          {activeImports[batch.batch_id] ? (
                            <span style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '3px 10px',
                              borderRadius: '12px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              background: '#dbeafe',
                              color: '#1d4ed8',
                              border: '1px solid #bfdbfe'
                            }}>
                              <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#2563eb', display: 'inline-block' }} />
                              Pushing ({activeImports[batch.batch_id].percent}%)
                            </span>
                          ) : (
                            <StatusBadge status={batch.status} />
                          )}
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
                              onClick={() => { setSelectedBatch(batch.batch_id); setActiveView('records'); setPage(1); }}
                              className="btn btn-secondary"
                              style={{ padding: '4px 8px', fontSize: '0.75rem', borderColor: '#3b82f6', color: '#1d4ed8' }}
                              title="Inspect parsed records for this batch"
                            >
                              <Table size={12} /> Records
                            </button>
                            <button
                              onClick={() => { setSelectedBatch(batch.batch_id); setActiveView('errors'); setPage(1); }}
                              className="btn btn-secondary"
                              style={{ padding: '4px 8px', fontSize: '0.75rem', borderColor: '#fca5a5', color: '#b91c1c' }}
                              title="Inspect error logs for this batch"
                            >
                              <AlertTriangle size={12} /> Errors
                            </button>
                            <Link 
                              to={`/logs?batch_id=${batch.batch_id}`} 
                              className="btn btn-secondary"
                              style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                              title="View batch audit logs"
                            >
                              <Terminal size={12} /> Logs
                            </Link>
                            {activeImports[batch.batch_id] ? (
                              <Link 
                                to={`/batches/${batch.batch_id}/results`} 
                                className="btn btn-primary"
                                style={{ padding: '4px 8px', fontSize: '0.75rem', background: '#2563eb', display: 'inline-flex', alignItems: 'center', gap: '3px' }}
                                title="View live database ingestion progress"
                              >
                                Live Monitor <ArrowRight size={11} />
                              </Link>
                            ) : (
                              <Link 
                                to={`/batches/${batch.batch_id}/results`} 
                                className="btn btn-primary"
                                style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                                title="Verification & downloads"
                              >
                                Results <ArrowRight size={11} />
                              </Link>
                            )}
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
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Raw Error Record Inspection Modal */}
      {inspectedRecord && (
        <Modal
          isOpen={Boolean(inspectedRecord)}
          onClose={() => setInspectedRecord(null)}
          onConfirm={() => setInspectedRecord(null)}
          title="Invalid APBS Record Diagnostic Inspection"
          description={`Line #${inspectedRecord.line_no || 'N/A'} in ${inspectedRecord._source_file || inspectedRecord.batch_id || 'source file'}`}
          confirmText="Close Inspector"
          showCancel={false}
          variant="secondary"
          details={
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px', background: '#fff1f2', padding: '12px', borderRadius: '6px', border: '1px solid #fecdd3' }}>
                <div><strong>Beneficiary:</strong> <span style={{ color: '#9f1239', fontWeight: 700 }}>{inspectedRecord.beneficiary_name || 'N/A'}</span></div>
                <div><strong>Aadhaar Number:</strong> <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{inspectedRecord.beneficiary_aadhaar_number || 'N/A'}</span></div>
                <div><strong>Credit Reference:</strong> <span style={{ fontFamily: 'var(--font-mono)' }}>{inspectedRecord.user_credit_reference || 'N/A'}</span></div>
                <div><strong>Amount (Paise):</strong> {inspectedRecord.amount || '0'}</div>
                <div><strong>Bank Account:</strong> <span style={{ fontFamily: 'var(--font-mono)' }}>{inspectedRecord.destination_bank_account_number || 'N/A'}</span></div>
                <div><strong>Bank IIN:</strong> <span style={{ fontFamily: 'var(--font-mono)' }}>{inspectedRecord.destination_bank_iin || 'N/A'}</span></div>
                <div><strong>File Source:</strong> {inspectedRecord._source_file || inspectedRecord.batch_id || 'N/A'}</div>
                <div><strong>Line #:</strong> {inspectedRecord.line_no || 'N/A'}</div>
              </div>

              <div style={{ background: '#fef2f2', padding: '10px 14px', borderRadius: '4px', border: '1px solid #fecaca' }}>
                <div style={{ color: '#b91c1c', fontWeight: 700, fontSize: '0.85rem', marginBottom: '2px' }}>
                  Failure Root Cause: {inspectedRecord.error_type || inspectedRecord.reason_code || 'INVALID_RECORD'}
                </div>
                <div style={{ color: '#475569', fontSize: '0.825rem' }}>
                  {inspectedRecord.error_detail || inspectedRecord.reason_code || 'Record violated APBS fixed-width parsing constraints.'}
                </div>
              </div>

              {inspectedRecord.raw_line && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#334155' }}>
                      Raw Fixed-Width Line Content ({inspectedRecord.raw_line.length} characters / Expected 177):
                    </span>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(inspectedRecord.raw_line);
                        showToast('Raw line copied to clipboard');
                      }}
                      className="btn btn-secondary"
                      style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                    >
                      Copy Raw String
                    </button>
                  </div>
                  <pre style={{
                    background: '#0f172a',
                    color: '#38bdf8',
                    padding: '12px',
                    borderRadius: '4px',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.75rem',
                    overflowX: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                    maxHeight: '160px',
                  }}>
                    {inspectedRecord.raw_line}
                  </pre>
                </div>
              )}
            </div>
          }
        />
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
