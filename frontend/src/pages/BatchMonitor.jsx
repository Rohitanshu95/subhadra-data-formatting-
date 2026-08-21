import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  CheckCircle2, 
  AlertTriangle, 
  Copy, 
  ArrowRight, 
  RefreshCw, 
  FileText, 
  Layers, 
  ShieldCheck
} from 'lucide-react';
import { getBatch, getBatchProgress, getBatchFiles } from '../services/api';
import MetricCard from '../components/MetricCard';
import StatusBadge from '../components/StatusBadge';

export default function BatchMonitor() {
  const { id: batchId } = useParams();
  const [batch, setBatch] = useState(null);
  const [progress, setProgress] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const pollIntervalRef = useRef(null);

  const fetchData = async () => {
    try {
      const [batchData, progressData, filesData] = await Promise.all([
        getBatch(batchId),
        getBatchProgress(batchId),
        getBatchFiles(batchId),
      ]);
      setBatch(batchData);
      setProgress(progressData);
      setFiles(filesData);
    } catch (err) {
      console.error('Failed to fetch batch data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // Live polling every 1.5 seconds
    pollIntervalRef.current = setInterval(async () => {
      try {
        const [progressData, batchData, filesData] = await Promise.all([
          getBatchProgress(batchId),
          getBatch(batchId),
          getBatchFiles(batchId),
        ]);
        setProgress(progressData);
        setBatch(batchData);
        setFiles(filesData);

        if (['COMPLETED', 'COMPLETED_WITH_ERRORS', 'VERIFIED', 'IMPORTED', 'FAILED'].includes(progressData.status)) {
          clearInterval(pollIntervalRef.current);
        }
      } catch (err) {
        console.error(err);
      }
    }, 1500);

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [batchId]);

  const isComplete = batch && ['COMPLETED', 'COMPLETED_WITH_ERRORS', 'VERIFIED', 'IMPORTED'].includes(batch.status);
  const pct = progress ? progress.progress_percentage : 0;

  return (
    <div className="app-container">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <h1 style={{ fontSize: '1.6rem', fontFamily: 'var(--font-mono)', color: '#0f172a' }}>{batchId}</h1>
            {batch && <StatusBadge status={batch.status} />}
          </div>
          <p style={{ color: '#64748b', fontSize: '0.875rem' }}>
            Real-Time Processing & Streaming Validation Status
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={fetchData} className="btn btn-secondary" title="Refresh">
            <RefreshCw size={14} /> Refresh
          </button>
          {isComplete && (
            <Link to={`/batches/${batchId}/results`} className="btn btn-primary">
              <ShieldCheck size={16} />
              Review & Verify Results
              <ArrowRight size={15} />
            </Link>
          )}
        </div>
      </div>

      {/* Progress Bar Card */}
      <div className="gov-card" style={{ padding: '20px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontWeight: 700, fontSize: '0.925rem', color: '#1e293b' }}>
            {isComplete ? 'Validation Processing Completed' : 'Streaming Files through Validation Engine...'}
          </span>
          <span style={{ fontWeight: 800, fontSize: '1.2rem', color: '#1d4ed8' }}>
            {pct}%
          </span>
        </div>

        <div className="progress-bar-bg" style={{ height: '10px', marginBottom: '12px' }}>
          <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#64748b' }}>
          <span>
            {progress ? `${progress.completed_files} of ${progress.total_files - progress.duplicate_files} processable files completed` : 'Loading...'}
          </span>
          <span>
            {progress && progress.duplicate_files > 0 ? `${progress.duplicate_files} duplicate file(s) skipped` : ''}
          </span>
        </div>
      </div>

      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <MetricCard 
          title="Valid Clean Records" 
          value={progress ? progress.valid_records.toLocaleString() : '0'} 
          subtitle="Ready for database commit" 
          icon={CheckCircle2} 
          color="#15803d" 
        />
        <MetricCard 
          title="Invalid Error Lines" 
          value={progress ? progress.invalid_records.toLocaleString() : '0'} 
          subtitle="Logged with line failure reasons" 
          icon={AlertTriangle} 
          color="#b91c1c" 
        />
        <MetricCard 
          title="Duplicate Files" 
          value={progress ? progress.duplicate_files : '0'} 
          subtitle="Exact SHA-256 match skipped" 
          icon={Copy} 
          color="#b45309" 
        />
        <MetricCard 
          title="Total Files in Batch" 
          value={batch ? batch.total_files : '0'} 
          subtitle={batch ? `${(batch.total_size / (1024 * 1024)).toFixed(2)} MB total size` : ''} 
          icon={Layers} 
          color="#1d4ed8" 
        />
      </div>

      {/* File List Table */}
      <div className="gov-card" style={{ padding: '20px' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px', color: '#0f172a' }}>
          <FileText size={17} color="#1d4ed8" />
          Batch Files Status ({files.length})
        </h2>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>File Name</th>
                <th>Status</th>
                <th>Records Read</th>
                <th>Valid Records</th>
                <th>Invalid Records</th>
                <th>Content SHA-256 Hash</th>
              </tr>
            </thead>
            <tbody>
              {files.map((file, idx) => (
                <tr key={idx}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <FileText size={15} color="#64748b" />
                      <span style={{ fontWeight: 600, color: '#0f172a' }}>{file.sanitized_filename}</span>
                    </div>
                  </td>
                  <td>
                    <StatusBadge status={file.status} />
                  </td>
                  <td style={{ fontWeight: 600 }}>
                    {file.record_count.toLocaleString()}
                  </td>
                  <td>
                    <span style={{ color: '#15803d', fontWeight: 700 }}>
                      {file.valid_count.toLocaleString()}
                    </span>
                  </td>
                  <td>
                    <span style={{ color: file.invalid_count > 0 ? '#b91c1c' : '#64748b', fontWeight: file.invalid_count > 0 ? 700 : 400 }}>
                      {file.invalid_count.toLocaleString()}
                    </span>
                  </td>
                  <td>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#475569' }}>
                      {file.sha256 ? `${file.sha256.substring(0, 16)}...` : 'Calculating...'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
