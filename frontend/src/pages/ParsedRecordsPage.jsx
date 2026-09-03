import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  Database, 
  ArrowLeft, 
  Search, 
  Filter, 
  ShieldCheck, 
  CheckCircle2, 
  AlertTriangle, 
  Copy, 
  RefreshCw, 
  FileText, 
  Shield, 
  Layers, 
  FileArchive, 
  Trash2,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight
} from 'lucide-react';
import { getParsedRecords, getBatch, deleteRecord } from '../services/api';
import StatusBadge from '../components/StatusBadge';
import Modal from '../components/Modal';
import Toast from '../components/Toast';

export default function ParsedRecordsPage() {
  const { id: batchId } = useParams();

  const [batch, setBatch] = useState(null);
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalPages, setTotalPages] = useState(1);
  const [dataSource, setDataSource] = useState('records_staging');
  const [loading, setLoading] = useState(true);

  // Filters
  const [successFlag, setSuccessFlag] = useState('');
  const [reasonCode, setReasonCode] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchBatchInfo = useCallback(async () => {
    try {
      const b = await getBatch(batchId);
      setBatch(b);
    } catch (err) {
      console.error('Failed to load batch info', err);
    }
  }, [batchId]);

  const fetchRecords = useCallback(async (forceRefresh = false) => {
    try {
      setLoading(true);
      const params = {
        page,
        page_size: pageSize,
      };
      if (successFlag !== '') params.success_flag = successFlag;
      if (reasonCode.trim() !== '') params.reason_code = reasonCode.trim();
      if (statusFilter !== 'ALL') params.status = statusFilter;
      if (debouncedSearch.trim() !== '') params.search = debouncedSearch.trim();
      if (forceRefresh) params.refresh = true;

      const data = await getParsedRecords(batchId, params);
      setRecords(data.records || []);
      setTotal(data.total || 0);
      setTotalPages(data.total_pages || 1);
      setDataSource(data.data_source || 'records_staging');
    } catch (err) {
      console.error('Failed to load parsed records', err);
    } finally {
      setLoading(false);
    }
  }, [batchId, page, pageSize, successFlag, reasonCode, statusFilter, debouncedSearch]);

  useEffect(() => {
    fetchBatchInfo();
  }, [fetchBatchInfo]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

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
            batch_id: batchId,
          });
          showToast(`Transaction for "${beneficiary}" deleted from database.`);
          closeModal();
          await fetchRecords();
        } catch (err) {
          showToast(`Failed to delete record: ${err.response?.data?.detail || err.message}`, 'error');
        } finally {
          setDeletingId(null);
        }
      }
    });
  };

  const handleClearFilters = () => {
    setSuccessFlag('');
    setReasonCode('');
    setStatusFilter('ALL');
    setSearchQuery('');
    setDebouncedSearch('');
    setPage(1);
  };

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

  const isProduction = dataSource.includes('Production Database');

  const renderPagination = (recordLabel = 'records') => {
    if (total === 0) return null;

    const startItem = (page - 1) * pageSize + 1;
    const endItem = Math.min(page * pageSize, total);

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
            Showing <strong style={{ color: '#0f172a' }}>{startItem.toLocaleString()}</strong> to <strong style={{ color: '#0f172a' }}>{endItem.toLocaleString()}</strong> of <strong style={{ color: '#0f172a' }}>{total.toLocaleString()}</strong> {recordLabel}
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
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Link to="/" style={{ color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.85rem', textDecoration: 'none' }}>
              <ArrowLeft size={14} /> Back to Dashboard
            </Link>
            <span style={{ color: '#cbd5e1' }}>/</span>
            <Link to={`/batches/${batchId}/results`} style={{ color: '#64748b', fontSize: '0.85rem', textDecoration: 'none' }}>
              Verification & Deliverables
            </Link>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
            <h1 style={{ fontSize: '1.6rem', fontFamily: 'var(--font-mono)', color: '#0f172a' }}>
              {batchId}
            </h1>
            {batch && <StatusBadge status={batch.status} />}
          </div>
          <p style={{ color: '#64748b', fontSize: '0.875rem' }}>
            Parsed APBS Records Inspector — Canonical 17-Field Layout with Complete Aadhaar & Account Numbers
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button 
            onClick={() => fetchRecords(true)} 
            className="btn btn-secondary"
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <a 
            href={`/api/batches/${batchId}/download/all`} 
            className="btn btn-primary"
            download
          >
            <FileArchive size={15} />
            Download ZIP
          </a>
        </div>
      </div>

      {/* Data Source & Privacy Banner */}
      <div className="gov-card" style={{
        padding: '14px 18px',
        marginBottom: '18px',
        borderLeft: isProduction ? '4px solid #15803d' : '4px solid #1d4ed8',
        backgroundColor: isProduction ? '#f0fdf4' : '#eff6ff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Shield size={20} color={isProduction ? '#15803d' : '#1d4ed8'} />
          <div>
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#0f172a' }}>
              Data Source: <span style={{ color: isProduction ? '#15803d' : '#1d4ed8' }}>{dataSource}</span>
            </div>
            <div style={{ fontSize: '0.8rem', color: '#475569' }}>
              Aadhaar & Bank Account numbers are masked on-screen (e.g. <code>********9012</code>) for compliance. Full records are restricted to authenticated export downloads.
            </div>
          </div>
        </div>
        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#334155' }}>
          Total Batch Records: <strong>{total.toLocaleString()}</strong>
        </div>
      </div>

      {/* Filter Card */}
      <div className="gov-card" style={{ padding: '16px', marginBottom: '20px' }}>
        <form onSubmit={handleFilterSubmit} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', alignItems: 'end' }}>
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

          {/* Reason Code Filter */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
              Reason Code
            </label>
            <input
              type="text"
              placeholder="e.g. 00, 01, 33"
              value={reasonCode}
              onChange={(e) => setReasonCode(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
            />
          </div>

          {/* Search Query */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
              Search (Aadhaar / Name / Ref)
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                placeholder="Search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ width: '100%', padding: '8px 10px 8px 30px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
              />
              <Search size={14} color="#94a3b8" style={{ position: 'absolute', left: '10px', top: '10px' }} />
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>
              <Filter size={14} /> Filter
            </button>
            <button type="button" onClick={handleClearFilters} className="btn btn-secondary">
              Clear
            </button>
          </div>
        </form>
      </div>

      {/* 18-Column Table Card */}
      <div className="gov-card" style={{ padding: '18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} color="#1d4ed8" />
            <h2 style={{ fontSize: '1.1rem', color: '#0f172a' }}>
              Parsed Records ({total.toLocaleString()})
            </h2>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: '#64748b' }}>
            <span>Page {page} of {totalPages} ({total.toLocaleString()} total)</span>
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
            <p style={{ fontWeight: 600, color: '#1e293b' }}>No parsed records match the filters</p>
            <p style={{ fontSize: '0.85rem' }}>Clear your search filters or check batch status.</p>
          </div>
        ) : (
          <div className="table-container" style={{ maxHeight: '620px', overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th style={{ whiteSpace: 'nowrap' }}>#</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Txn Code (1)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Dest Bank IIN (2)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Dest Acc Type (3)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Ledger Folio (4)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Beneficiary Aadhaar (5)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Beneficiary Name (6)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Sponsor Bank IIN (7)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>User Number (8)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Narration (9)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Credit Ref (10)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Amount (Paise) (11)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Item Seq (12)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Checksum (13)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Success Flag (14)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Filler (15)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Reason (16)</th>
                  <th style={{ whiteSpace: 'nowrap' }}>Dest Account No (17)</th>
                  <th style={{ whiteSpace: 'nowrap', textAlign: 'center' }}>DB Status (18)</th>
                  <th style={{ whiteSpace: 'nowrap', textAlign: 'center' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, idx) => {
                  const isInvalid = (r.status || '').toUpperCase() === 'INVALID';
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
                        {r.success_flag === '1' ? (
                          <span style={{ color: '#15803d', fontWeight: 700 }}>1 (Credited)</span>
                        ) : r.success_flag === '0' ? (
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
                        {getRecordStatusBadge(r.status)}
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
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination bar */}
        {renderPagination('records')}
      </div>

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
