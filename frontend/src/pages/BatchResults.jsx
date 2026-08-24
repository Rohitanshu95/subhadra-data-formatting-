import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { 
  ShieldCheck, 
  Database, 
  Download, 
  FileText, 
  AlertTriangle, 
  CheckCircle2, 
  FileArchive,
  RefreshCw,
  Eye,
  Check,
  Loader2,
  Trash2
} from 'lucide-react';
import { 
  getBatch, 
  verifyBatch, 
  importBatchToSql, 
  previewCleanRecords, 
  previewErrorRecords, 
  getBatchSummaryText,
  deleteBatch
} from '../services/api';
import StatusBadge from '../components/StatusBadge';
import Modal from '../components/Modal';
import Toast from '../components/Toast';

export default function BatchResults() {
  const { id: batchId } = useParams();
  const [batch, setBatch] = useState(null);
  const [activeTab, setActiveTab] = useState('clean'); // 'clean', 'errors', 'summary'
  const [cleanRecords, setCleanRecords] = useState([]);
  const [errorRecords, setErrorRecords] = useState([]);
  const [summaryText, setSummaryText] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);

  const fetchAllData = async () => {
    try {
      setLoading(true);
      const [batchData, cleanData, errorsData, summaryData] = await Promise.all([
        getBatch(batchId),
        previewCleanRecords(batchId, 30),
        previewErrorRecords(batchId, 30),
        getBatchSummaryText(batchId).catch(() => 'Summary report not available.'),
      ]);
      setBatch(batchData);
      setCleanRecords(cleanData);
      setErrorRecords(errorsData);
      setSummaryText(summaryData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, [batchId]);

  const [modalConfig, setModalConfig] = useState({
    isOpen: false,
    title: '',
    description: '',
    confirmText: 'Confirm',
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

  const handleVerify = async () => {
    try {
      setActionLoading(true);
      const updated = await verifyBatch(batchId);
      setBatch(updated);
      showToast(`Batch ${batchId} verified successfully.`);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to verify batch', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const promptImportToSql = () => {
    setModalConfig({
      isOpen: true,
      title: 'Approve & Import to SQL Database',
      description: 'Are you sure you want to commit all valid records into the production SQL database? This will also automatically clean up staged files.',
      confirmText: 'Approve & Commit to Database',
      variant: 'success',
      details: (
        <div>
          <div><strong>Batch:</strong> <span style={{ fontFamily: 'var(--font-mono)' }}>{batchId}</span></div>
          <div><strong>Valid Records to Commit:</strong> {batch?.valid_records?.toLocaleString() || 0}</div>
        </div>
      ),
      onConfirm: async () => {
        try {
          setActionLoading(true);
          const res = await importBatchToSql(batchId);
          setImportResult(res);
          const updated = await getBatch(batchId);
          setBatch(updated);
          showToast(`Successfully committed ${res.total_imported} records to SQL database.`);
          closeModal();
        } catch (err) {
          showToast(err.response?.data?.detail || 'Failed to import batch to SQL', 'error');
        } finally {
          setActionLoading(false);
        }
      }
    });
  };

  const isVerified = batch?.status === 'VERIFIED';
  const isImported = batch?.status === 'IMPORTED';

  const navigate = useNavigate();

  const promptDeleteBatch = () => {
    setModalConfig({
      isOpen: true,
      title: 'Delete File Confirmation',
      description: `Are you sure you want to permanently delete File "${batchId}"? This will remove all associated files, audit logs, and SQL database transactions.`,
      confirmText: 'Delete File Entry',
      variant: 'danger',
      details: (
        <div style={{ color: '#b91c1c' }}>
          ⚠️ All transactions from this file in the database will be erased.
        </div>
      ),
      onConfirm: async () => {
        try {
          setActionLoading(true);
          await deleteBatch(batchId);
          closeModal();
          navigate('/');
        } catch (err) {
          showToast(`Failed to delete file: ${err.response?.data?.detail || err.message}`, 'error');
          setActionLoading(false);
        }
      }
    });
  };

  return (
    <div className="app-container">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <h1 style={{ fontSize: '1.6rem', fontFamily: 'var(--font-mono)', color: '#0f172a' }}>{batchId}</h1>
            {batch && <StatusBadge status={batch.status} />}
          </div>
          <p style={{ color: '#64748b', fontSize: '0.875rem' }}>
            Human Verification Checkpoint & Output Deliverables
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <a 
            href={`/api/batches/${batchId}/download/all`} 
            className="btn btn-primary"
            download
          >
            <FileArchive size={15} />
            Download Results ZIP Package
          </a>
          <button
            onClick={promptDeleteBatch}
            disabled={actionLoading}
            className="btn btn-danger"
            style={{ padding: '8px 14px' }}
            title="Permanently delete file and its database records"
          >
            <Trash2 size={15} /> Delete File
          </button>
        </div>
      </div>

      {/* Human Verification Action Banner */}
      <div className="gov-card" style={{
        padding: '20px',
        marginBottom: '24px',
        borderLeft: isImported ? '4px solid #15803d' : isVerified ? '4px solid #7e22ce' : '4px solid #1d4ed8',
        backgroundColor: isImported ? '#f0fdf4' : isVerified ? '#faf5ff' : '#f8fafc',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
          <div>
            <h3 style={{ fontSize: '1.15rem', color: '#0f172a', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldCheck size={18} color={isImported ? '#15803d' : '#1d4ed8'} />
              {isImported ? 'Database Import Completed' : isVerified ? 'Batch Verified — Ready for SQL Commit' : 'Official Verification & Review Checkpoint'}
            </h3>
            <p style={{ color: '#475569', fontSize: '0.875rem' }}>
              {isImported 
                ? 'All clean APBS transactions have been idempotently committed to the SQL database.' 
                : isVerified 
                ? 'Batch is authorized. Click below to commit all valid records to the database.' 
                : 'Inspect sample records and error logs below before signing off and importing to SQL.'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {!isVerified && !isImported && (
              <button 
                onClick={handleVerify} 
                className="btn btn-secondary"
                disabled={actionLoading}
                style={{ borderColor: '#7e22ce', color: '#7e22ce' }}
              >
                {actionLoading ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
                Sign-off & Verify Batch
              </button>
            )}

            {!isImported && (
              <button 
                onClick={promptImportToSql} 
                className="btn btn-success"
                disabled={actionLoading}
              >
                {actionLoading ? <Loader2 size={15} className="animate-spin" /> : <Database size={15} />}
                Approve & Import to SQL
              </button>
            )}
          </div>
        </div>

        {importResult && (
          <div style={{
            marginTop: '14px',
            padding: '10px 14px',
            background: '#ffffff',
            border: '1px solid #86efac',
            borderRadius: '4px',
            fontSize: '0.875rem',
            color: '#166534',
            display: 'flex',
            gap: '20px',
            flexWrap: 'wrap',
          }}>
            <span>• Scanned: <strong>{importResult.total_processed?.toLocaleString()}</strong></span>
            <span>• Written to Database: <strong>{importResult.total_imported?.toLocaleString()}</strong></span>
            <span>• Duplicates Diverted: <strong>{importResult.total_duplicates?.toLocaleString()}</strong></span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', borderBottom: '2px solid #cbd5e1', marginBottom: '20px' }}>
        <button
          onClick={() => setActiveTab('clean')}
          style={{
            padding: '10px 18px',
            background: activeTab === 'clean' ? '#ffffff' : 'transparent',
            border: '1px solid',
            borderColor: activeTab === 'clean' ? '#cbd5e1 #cbd5e1 transparent #cbd5e1' : 'transparent',
            borderTopLeftRadius: '4px',
            borderTopRightRadius: '4px',
            color: activeTab === 'clean' ? '#1d4ed8' : '#475569',
            fontWeight: 700,
            fontSize: '0.875rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginBottom: '-2px',
          }}
        >
          <CheckCircle2 size={15} color="#15803d" />
          Clean Records Preview ({cleanRecords.length})
        </button>

        <button
          onClick={() => setActiveTab('errors')}
          style={{
            padding: '10px 18px',
            background: activeTab === 'errors' ? '#ffffff' : 'transparent',
            border: '1px solid',
            borderColor: activeTab === 'errors' ? '#cbd5e1 #cbd5e1 transparent #cbd5e1' : 'transparent',
            borderTopLeftRadius: '4px',
            borderTopRightRadius: '4px',
            color: activeTab === 'errors' ? '#b91c1c' : '#475569',
            fontWeight: 700,
            fontSize: '0.875rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginBottom: '-2px',
          }}
        >
          <AlertTriangle size={15} color="#b91c1c" />
          Error Logs Preview ({errorRecords.length})
        </button>

        <button
          onClick={() => setActiveTab('summary')}
          style={{
            padding: '10px 18px',
            background: activeTab === 'summary' ? '#ffffff' : 'transparent',
            border: '1px solid',
            borderColor: activeTab === 'summary' ? '#cbd5e1 #cbd5e1 transparent #cbd5e1' : 'transparent',
            borderTopLeftRadius: '4px',
            borderTopRightRadius: '4px',
            color: activeTab === 'summary' ? '#1d4ed8' : '#475569',
            fontWeight: 700,
            fontSize: '0.875rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginBottom: '-2px',
          }}
        >
          <FileText size={15} color="#1d4ed8" />
          Summary Report (TXT)
        </button>
      </div>

      {/* Tab 1: Clean Records Preview */}
      {activeTab === 'clean' && (
        <div className="gov-card" style={{ padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.825rem', color: '#64748b' }}>
              Sample clean records extracted according to the canonical 17-field fixed-width schema (Aadhaar/Accounts Masked).
            </span>
          </div>

          {cleanRecords.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '36px', color: '#64748b', background: '#f8fafc', borderRadius: '4px' }}>
              No clean records found in this batch.
            </div>
          ) : (
            <div className="table-container" style={{ maxHeight: '480px' }}>
              <table>
                <thead>
                  <tr>
                    <th>Txn Code</th>
                    <th>Dest Bank IIN</th>
                    <th>Aadhaar Number</th>
                    <th>Beneficiary Name</th>
                    <th>Amount (Paise)</th>
                    <th>Credit Reference</th>
                    <th>Status</th>
                    <th>Reason</th>
                    <th>Source File</th>
                  </tr>
                </thead>
                <tbody>
                  {cleanRecords.map((r, idx) => (
                    <tr key={idx}>
                      <td><span className="badge badge-ready">{r.apbs_transaction_code}</span></td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{r.destination_bank_iin}</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{r.beneficiary_aadhaar_number}</td>
                      <td style={{ fontWeight: 600, color: '#0f172a' }}>{r.beneficiary_name || '—'}</td>
                      <td style={{ fontWeight: 700, color: '#15803d' }}>{r.amount}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{r.user_credit_reference}</td>
                      <td>{r.success_flag === '1' ? <span style={{ color: '#15803d', fontWeight: 600 }}>Credited (1)</span> : <span style={{ color: '#b91c1c', fontWeight: 600 }}>Returned (0)</span>}</td>
                      <td>{r.reason_code}</td>
                      <td style={{ fontSize: '0.75rem', color: '#64748b' }}>{r._source_file}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Error Records Preview */}
      {activeTab === 'errors' && (
        <div className="gov-card" style={{ padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.825rem', color: '#64748b' }}>
              Validation and length failure log entries with line numbers and parsed failure details.
            </span>
          </div>

          {errorRecords.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '36px', color: '#15803d', fontWeight: 700, background: '#f0fdf4', borderRadius: '4px', border: '1px solid #bbf7d0' }}>
              ✓ Zero errors encountered in this batch!
            </div>
          ) : (
            <div className="table-container" style={{ maxHeight: '480px' }}>
              <table>
                <thead>
                  <tr>
                    <th>Line #</th>
                    <th>Error Classification</th>
                    <th>Failure Reason</th>
                    <th>Source File</th>
                  </tr>
                </thead>
                <tbody>
                  {errorRecords.map((err, idx) => (
                    <tr key={idx}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{err.line || '—'}</td>
                      <td><span className="badge badge-failed">{err.error || 'ERROR'}</span></td>
                      <td style={{ color: '#b91c1c', fontWeight: 500 }}>{err.detail || err.raw_entry}</td>
                      <td style={{ fontSize: '0.75rem', color: '#64748b' }}>{err._source_file}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Summary Report */}
      {activeTab === 'summary' && (
        <div className="gov-card" style={{ padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
            <span style={{ fontSize: '0.825rem', color: '#64748b' }}>
              Official batch summary text report generated at storage/logs/{batchId}/batch_summary.txt
            </span>
            <a 
              href={`/api/batches/${batchId}/download/summary`} 
              className="btn btn-secondary" 
              style={{ padding: '5px 12px', fontSize: '0.8rem' }}
              download
            >
              <Download size={14} /> Download Summary (TXT)
            </a>
          </div>

          <pre style={{
            background: '#f8fafc',
            padding: '16px',
            borderRadius: '4px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.825rem',
            color: '#1e293b',
            overflowX: 'auto',
            lineHeight: 1.5,
            border: '1px solid #cbd5e1',
          }}>
            {summaryText}
          </pre>
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
        loading={actionLoading}
      />

      {/* Custom Application Toast Notification */}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
