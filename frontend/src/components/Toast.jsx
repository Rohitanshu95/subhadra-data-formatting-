import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export default function Toast({ toast, onClose }) {
  if (!toast) return null;

  const isError = toast.type === 'error';
  const isSuccess = toast.type === 'success';

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 10000,
        backgroundColor: '#ffffff',
        border: `1px solid ${isError ? '#fca5a5' : isSuccess ? '#86efac' : '#cbd5e1'}`,
        borderLeft: `4px solid ${isError ? '#dc2626' : isSuccess ? '#16a34a' : '#2563eb'}`,
        borderRadius: '6px',
        padding: '12px 16px',
        boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        minWidth: '320px',
        maxWidth: '480px',
        animation: 'slideUp 0.2s ease-out',
      }}
    >
      {isSuccess && <CheckCircle2 size={20} color="#16a34a" style={{ flexShrink: 0 }} />}
      {isError && <AlertCircle size={20} color="#dc2626" style={{ flexShrink: 0 }} />}
      {!isSuccess && !isError && <Info size={20} color="#2563eb" style={{ flexShrink: 0 }} />}

      <div style={{ flex: 1, fontSize: '0.875rem', color: '#1e293b' }}>
        {toast.message}
      </div>

      <button
        onClick={onClose}
        style={{
          background: 'none',
          border: 'none',
          color: '#94a3b8',
          cursor: 'pointer',
          padding: '2px',
        }}
      >
        <X size={16} />
      </button>
    </div>
  );
}
