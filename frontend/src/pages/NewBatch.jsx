import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  UploadCloud, 
  FileText, 
  Trash2, 
  AlertCircle, 
  CheckCircle2, 
  ArrowRight,
  ShieldCheck,
  Loader2,
  FolderUp,
  XCircle,
  HelpCircle,
  HardDrive
} from 'lucide-react';
import { createBatch, uploadBatchFiles, processBatch } from '../services/api';

const MAX_FILES = 100;
const MAX_SIZE_BYTES = 3 * 1024 * 1024 * 1024; // 3 GB

export default function NewBatch() {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgressText, setUploadProgressText] = useState('');
  const fileInputRef = useRef(null);

  const totalSize = files.reduce((acc, f) => acc + f.size, 0);
  const totalSizeMB = (totalSize / (1024 * 1024)).toFixed(2);
  const totalSizeGB = (totalSize / (1024 * 1024 * 1024)).toFixed(3);

  const handleFilesAdded = (incomingFiles) => {
    setError(null);
    const newFiles = Array.from(incomingFiles);
    
    // Check duplicates in selected list by name
    const existingNames = new Set(files.map(f => f.name));
    const uniqueIncoming = newFiles.filter(f => !existingNames.has(f.name));
    
    const combined = [...files, ...uniqueIncoming];

    if (combined.length > MAX_FILES) {
      setError(`Batch file limit exceeded: Maximum ${MAX_FILES} files allowed per batch.`);
      return;
    }

    const combinedSize = combined.reduce((acc, f) => acc + f.size, 0);
    if (combinedSize > MAX_SIZE_BYTES) {
      setError(`Batch size limit exceeded: Total size must be under 3.0 GB.`);
      return;
    }

    setFiles(combined);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesAdded(e.dataTransfer.files);
    }
  };

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const clearAllFiles = () => {
    setFiles([]);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleStartProcessing = async () => {
    if (files.length === 0) {
      setError('Please select or drag-and-drop at least one APBS file to proceed.');
      return;
    }

    try {
      setUploading(true);
      setError(null);
      
      // 1. Create Batch
      setUploadProgressText('Step 1/3: Allocating buffered processing queue...');
      const batch = await createBatch();
      const batchId = batch.batch_id;

      // 2. Stream Upload Files
      setUploadProgressText(`Step 2/3: Streaming ${files.length} file(s) & computing SHA-256 integrity hashes...`);
      await uploadBatchFiles(batchId, files);

      // 3. Trigger Asynchronous Processing
      setUploadProgressText('Step 3/3: Buffering records & starting high-performance validation engine...');
      await processBatch(batchId);

      // 4. Redirect to Live Monitor
      navigate(`/batches/${batchId}`);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || err.message || 'Failed to start file processing.');
      setUploading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Header section */}
      <div style={{ marginBottom: '22px' }}>
        <h1 style={{ fontSize: '1.75rem', color: '#0f172a', marginBottom: '4px' }}>
          Upload APBS Response File
        </h1>
        <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
          Upload APBS 177-character fixed-width response files for automated parsing, deduplication, and database verification.
        </p>
      </div>

      {error && (
        <div style={{
          background: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: '6px',
          padding: '14px 18px',
          color: '#b91c1c',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          marginBottom: '22px',
          fontSize: '0.875rem',
        }}>
          <AlertCircle size={20} />
          <span style={{ fontWeight: 600 }}>{error}</span>
        </div>
      )}

      {/* Grid: Upload Zone on Left / File Queue & Specifications on Right */}
      <div style={{ display: 'grid', gridTemplateColumns: files.length > 0 ? '1.1fr 1fr' : '1fr', gap: '20px', marginBottom: '24px' }}>
        
        {/* Upload Drop Zone Card */}
        <div 
          className="gov-card"
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            padding: '50px 24px',
            textAlign: 'center',
            cursor: 'pointer',
            borderStyle: 'dashed',
            borderWidth: '2px',
            borderColor: isDragging ? '#1d4ed8' : '#cbd5e1',
            background: isDragging ? '#eff6ff' : '#ffffff',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '340px',
          }}
        >
          <input 
            type="file" 
            multiple 
            ref={fileInputRef} 
            style={{ display: 'none' }} 
            onChange={(e) => {
              if (e.target.files) handleFilesAdded(e.target.files);
            }} 
          />
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            background: '#eff6ff',
            color: '#1d4ed8',
            border: '1px solid #bfdbfe',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '16px',
          }}>
            <UploadCloud size={32} />
          </div>
          
          <h3 style={{ fontSize: '1.25rem', color: '#0f172a', marginBottom: '8px' }}>
            Drag and drop APBS data files here
          </h3>
          <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '20px' }}>
            or <span style={{ color: '#1d4ed8', fontWeight: 700, textDecoration: 'underline' }}>Browse from your computer</span>
          </p>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: '#475569', background: '#f8fafc', padding: '6px 12px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
              ✓ Max 100 Files
            </span>
            <span style={{ fontSize: '0.8rem', color: '#475569', background: '#f8fafc', padding: '6px 12px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
              ✓ Max 3.0 GB Total
            </span>
            <span style={{ fontSize: '0.8rem', color: '#475569', background: '#f8fafc', padding: '6px 12px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
              ✓ 177-Char Fixed Width
            </span>
          </div>
        </div>

        {/* Selected File Queue & Summary */}
        {files.length > 0 && (
          <div className="gov-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', color: '#0f172a' }}>
                  Selected Files Queue ({files.length} / {MAX_FILES})
                </h3>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  Total Payload Size: <strong>{totalSize > 1024 * 1024 * 1024 ? `${totalSizeGB} GB` : `${totalSizeMB} MB`}</strong>
                </span>
              </div>

              <button 
                type="button"
                onClick={clearAllFiles}
                className="btn btn-secondary"
                style={{ padding: '4px 10px', fontSize: '0.75rem', color: '#b91c1c' }}
                title="Clear all selected files"
              >
                <XCircle size={13} /> Clear All
              </button>
            </div>

            <div style={{ flex: 1, maxHeight: '280px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', paddingRight: '4px' }}>
              {files.map((file, idx) => (
                <div 
                  key={idx}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '4px',
                    fontSize: '0.875rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                    <FileText size={16} color="#1d4ed8" style={{ flexShrink: 0 }} />
                    <span style={{ fontWeight: 600, color: '#1e293b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '280px' }} title={file.name}>
                      {file.name}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
                    <span style={{ color: '#64748b', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                      {(file.size / 1024).toFixed(1)} KB
                    </span>
                    <button 
                      onClick={(e) => { e.stopPropagation(); removeFile(idx); }}
                      style={{ background: 'none', border: 'none', color: '#b91c1c', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                      title="Remove file"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ marginTop: '14px', paddingTop: '12px', borderTop: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#15803d' }}>
              <ShieldCheck size={16} />
              <span>SHA-256 collision hashing and per-record validation will be performed automatically.</span>
            </div>
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="gov-card" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
        <button 
          onClick={() => navigate('/')} 
          className="btn btn-secondary"
          disabled={uploading}
        >
          Cancel & Return to Dashboard
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {uploading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#1d4ed8', fontSize: '0.9rem', fontWeight: 600 }}>
              <Loader2 size={18} className="animate-spin" />
              <span>{uploadProgressText}</span>
            </div>
          )}

          <button 
            onClick={handleStartProcessing} 
            className="btn btn-primary"
            disabled={files.length === 0 || uploading}
            style={{ padding: '10px 28px', fontSize: '0.95rem' }}
          >
            {uploading ? 'Processing File(s)...' : `Start File Processing (${files.length} file${files.length !== 1 ? 's' : ''})`}
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
