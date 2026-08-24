import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { 
  FileText, 
  RefreshCw, 
  Search, 
  Filter, 
  Layers, 
  AlertCircle, 
  Terminal, 
  ArrowLeft,
  Copy,
  Check,
  Calendar,
  Clock
} from 'lucide-react';
import { getLogs, listBatches } from '../services/api';

export default function LogsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialBatchId = searchParams.get('batch_id') || '';

  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  // Filters
  const [batchId, setBatchId] = useState(initialBatchId);
  const [level, setLevel] = useState('ALL');
  const [fileId, setFileId] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [availableBatches, setAvailableBatches] = useState([]);

  // Load available batches for dropdown suggestion
  useEffect(() => {
    listBatches()
      .then((data) => setAvailableBatches(data || []))
      .catch(() => {});
  }, []);

  const fetchLogsData = useCallback(async () => {
    try {
      setLoading(true);
      const params = {
        page,
        page_size: pageSize,
      };
      if (batchId.trim()) params.batch_id = batchId.trim();
      if (level !== 'ALL') params.level = level;
      if (fileId.trim()) params.file_id = fileId.trim();
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const data = await getLogs(params);
      setLogs(data.items || []);
      setTotal(data.total || 0);
      setTotalPages(data.total_pages || 1);
    } catch (err) {
      console.error('Failed to load logs', err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, batchId, level, fileId, searchQuery]);

  useEffect(() => {
    fetchLogsData();
  }, [fetchLogsData]);

  // Auto-refresh interval
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchLogsData();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchLogsData]);

  const handleFilterSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    if (batchId) {
      setSearchParams({ batch_id: batchId });
    } else {
      setSearchParams({});
    }
    fetchLogsData();
  };

  const handleClearFilters = () => {
    setBatchId('');
    setLevel('ALL');
    setFileId('');
    setSearchQuery('');
    setSearchParams({});
    setPage(1);
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getLevelBadge = (lvl) => {
    const l = (lvl || '').toUpperCase();
    if (l === 'ERROR' || l === 'CRITICAL' || l === 'FAILED') {
      return <span style={{ background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>ERROR</span>;
    }
    if (l === 'RECORD' || l === 'BATCH') {
      return <span style={{ background: '#faf5ff', color: '#7e22ce', border: '1px solid #e9d5ff', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>RECORD</span>;
    }
    if (l === 'INDIVIDUAL DATA' || l === 'FILE') {
      return <span style={{ background: '#f0fdfa', color: '#0f766e', border: '1px solid #99f6e4', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>INDIVIDUAL DATA</span>;
    }
    if (l === 'APPLICATION') {
      return <span style={{ background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>APPLICATION</span>;
    }
    return <span style={{ background: '#f8fafc', color: '#475569', border: '1px solid #e2e8f0', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>{l || 'INFO'}</span>;
  };

  return (
    <div className="app-container">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Link to="/" style={{ color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.85rem', textDecoration: 'none' }}>
              <ArrowLeft size={14} /> Back to Dashboard
            </Link>
          </div>
          <h1 style={{ fontSize: '1.75rem', color: '#0f172a', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Terminal size={24} color="#1d4ed8" />
            System & Audit Logs
          </h1>
          <p style={{ color: '#64748b', fontSize: '0.875rem' }}>
            Structured operational logs (Application, Record, Individual Data, and Error events)
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#475569', cursor: 'pointer', background: '#ffffff', padding: '6px 12px', borderRadius: '4px', border: '1px solid #cbd5e1' }}>
            <input 
              type="checkbox" 
              checked={autoRefresh} 
              onChange={(e) => setAutoRefresh(e.target.checked)} 
            />
            Auto-refresh (5s)
          </label>
          <button 
            onClick={fetchLogsData} 
            className="btn btn-secondary"
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Filter Bar Card */}
      <div className="gov-card" style={{ padding: '16px', marginBottom: '20px' }}>
        <form onSubmit={handleFilterSubmit} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', alignItems: 'end' }}>
          {/* Level Filter */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
              Log Tier / Level
            </label>
            <select
              value={level}
              onChange={(e) => {
                setLevel(e.target.value);
                setPage(1);
              }}
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: '4px',
                border: '1px solid #cbd5e1',
                fontSize: '0.875rem',
                backgroundColor: '#ffffff',
              }}
            >
              <option value="ALL">All Tiers & Levels</option>
              <option value="APPLICATION">Application Tier</option>
              <option value="RECORD">Record Tier</option>
              <option value="INDIVIDUAL DATA">Individual Data Tier</option>
              <option value="ERROR">Error Events</option>
              <option value="INFO">Info</option>
            </select>
          </div>

          {/* Batch ID Filter */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
              File Identifier
            </label>
            <input
              type="text"
              placeholder="e.g. FILE-20260820-..."
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              list="batches-list"
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: '4px',
                border: '1px solid #cbd5e1',
                fontSize: '0.875rem',
              }}
            />
            <datalist id="batches-list">
              {availableBatches.map((b) => (
                <option key={b.batch_id} value={b.batch_id} />
              ))}
            </datalist>
          </div>

          {/* Search Message */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '4px' }}>
              Search Message Text
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                placeholder="Search keywords..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px 8px 30px',
                  borderRadius: '4px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.875rem',
                }}
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

        {batchId && (
          <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#1d4ed8' }}>
            <span>Filtered by batch: <strong>{batchId}</strong></span>
            <button 
              onClick={() => { setBatchId(''); setSearchParams({}); }}
              style={{ background: 'none', border: 'none', color: '#b91c1c', cursor: 'pointer', fontSize: '0.8rem', textDecoration: 'underline' }}
            >
              Remove filter
            </button>
          </div>
        )}
      </div>

      {/* Logs Table Card */}
      <div className="gov-card" style={{ padding: '18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} color="#1d4ed8" />
            <h2 style={{ fontSize: '1.1rem', color: '#0f172a' }}>
              Log Entries ({total.toLocaleString()})
            </h2>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: '#64748b' }}>
            <span>Page {page} of {totalPages}</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '0.8rem' }}
            >
              <option value={25}>25 / page</option>
              <option value={50}>50 / page</option>
              <option value={100}>100 / page</option>
            </select>
          </div>
        </div>

        {logs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '48px 20px', color: '#64748b', background: '#f8fafc', borderRadius: '4px' }}>
            <Terminal size={32} color="#94a3b8" style={{ margin: '0 auto 8px' }} />
            <p style={{ fontWeight: 600, color: '#1e293b' }}>No log entries found</p>
            <p style={{ fontSize: '0.85rem' }}>Try adjusting your filters or upload a new batch to generate activity.</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '180px' }}>Timestamp</th>
                  <th style={{ width: '130px' }}>Tier / Level</th>
                  <th style={{ width: '190px' }}>File Identifier</th>
                  <th style={{ width: '140px' }}>File Context</th>
                  <th>Log Message</th>
                  <th style={{ width: '60px', textAlign: 'center' }}>Copy</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td style={{ fontSize: '0.785rem', color: '#475569', whiteSpace: 'nowrap' }}>
                      {log.timestamp ? new Date(log.timestamp).toLocaleString() : '—'}
                    </td>
                    <td>{getLevelBadge(log.level)}</td>
                    <td>
                      {log.batch_id ? (
                        <span 
                          onClick={() => { setBatchId(log.batch_id); setSearchParams({ batch_id: log.batch_id }); }}
                          style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: '#1d4ed8', cursor: 'pointer', fontWeight: 600 }}
                          title="Filter by this batch"
                        >
                          {log.batch_id}
                        </span>
                      ) : (
                        <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>System</span>
                      )}
                    </td>
                    <td style={{ fontSize: '0.785rem', color: '#475569' }}>
                      {log.file_id || '—'}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: '#1e293b', wordBreak: 'break-word' }}>
                      {log.message}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        onClick={() => copyToClipboard(log.message, log.id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: copiedId === log.id ? '#15803d' : '#94a3b8',
                          cursor: 'pointer',
                          padding: '4px',
                        }}
                        title="Copy log text"
                      >
                        {copiedId === log.id ? <Check size={14} /> : <Copy size={14} />}
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
              Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, total)} of {total} records
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
    </div>
  );
}
