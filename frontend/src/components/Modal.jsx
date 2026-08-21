import React, { useEffect } from 'react';
import { AlertTriangle, Trash2, CheckCircle2, HelpCircle, X, ShieldAlert } from 'lucide-react';

export default function Modal({
  isOpen,
  onClose,
  onConfirm,
  title = "Confirm Action",
  description = "Are you sure you want to perform this action?",
  confirmText = "Confirm",
  cancelText = "Cancel",
  variant = "danger", // 'danger' | 'warning' | 'primary' | 'success'
  details = null,
  loading = false,
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen && !loading) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, loading, onClose]);

  if (!isOpen) return null;

  const getVariantStyles = () => {
    switch (variant) {
      case 'danger':
        return {
          icon: <Trash2 size={24} color="#dc2626" />,
          iconBg: '#fee2e2',
          btnBg: '#dc2626',
          btnHoverBg: '#b91c1c',
          btnColor: '#ffffff',
        };
      case 'warning':
        return {
          icon: <AlertTriangle size={24} color="#d97706" />,
          iconBg: '#fef3c7',
          btnBg: '#d97706',
          btnHoverBg: '#b45309',
          btnColor: '#ffffff',
        };
      case 'success':
        return {
          icon: <CheckCircle2 size={24} color="#16a34a" />,
          iconBg: '#dcfce7',
          btnBg: '#16a34a',
          btnHoverBg: '#15803d',
          btnColor: '#ffffff',
        };
      default:
        return {
          icon: <ShieldAlert size={24} color="#2563eb" />,
          iconBg: '#dbeafe',
          btnBg: '#2563eb',
          btnHoverBg: '#1d4ed8',
          btnColor: '#ffffff',
        };
    }
  };

  const vStyle = getVariantStyles();

  return (
    <div 
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px',
        animation: 'fadeIn 0.15s ease-out',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) onClose();
      }}
    >
      <div 
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '8px',
          width: '100%',
          maxWidth: '480px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
          animation: 'scaleIn 0.15s ease-out',
        }}
      >
        {/* Modal Header & Icon */}
        <div style={{ padding: '24px 24px 16px', display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '50%',
            backgroundColor: vStyle.iconBg,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            {vStyle.icon}
          </div>

          <div style={{ flex: 1 }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#0f172a', marginBottom: '6px' }}>
              {title}
            </h3>
            <p style={{ fontSize: '0.875rem', color: '#64748b', lineHeight: 1.5 }}>
              {description}
            </p>
          </div>

          <button
            onClick={onClose}
            disabled={loading}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '4px',
              borderRadius: '4px',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Details / Highlights Card */}
        {details && (
          <div style={{
            margin: '0 24px 16px',
            padding: '12px 16px',
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '6px',
            fontSize: '0.85rem',
            color: '#334155',
          }}>
            {details}
          </div>
        )}

        {/* Modal Footer Actions */}
        <div style={{
          padding: '14px 24px',
          backgroundColor: '#f8fafc',
          borderTop: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '10px',
        }}>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="btn btn-secondary"
            style={{ padding: '8px 16px', fontSize: '0.875rem' }}
          >
            {cancelText}
          </button>

          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            style={{
              padding: '8px 18px',
              fontSize: '0.875rem',
              fontWeight: 600,
              borderRadius: '4px',
              border: 'none',
              cursor: loading ? 'not-allowed' : 'pointer',
              backgroundColor: vStyle.btnBg,
              color: vStyle.btnColor,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'background-color 0.15s ease',
            }}
          >
            {loading ? 'Processing...' : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
