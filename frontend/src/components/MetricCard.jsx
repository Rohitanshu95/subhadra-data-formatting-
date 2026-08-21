import React from 'react';

export default function MetricCard({ title, value, subtitle, icon: Icon, color = '#1d4ed8' }) {
  return (
    <div className="gov-card" style={{ padding: '18px 20px', position: 'relative', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <span style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#475569' }}>
          {title}
        </span>
        {Icon && (
          <div style={{
            width: '34px',
            height: '34px',
            borderRadius: '4px',
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: color,
          }}>
            <Icon size={18} />
          </div>
        )}
      </div>

      <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#0f172a', marginBottom: '4px' }}>
        {value}
      </div>

      {subtitle && (
        <div style={{ fontSize: '0.775rem', color: '#64748b' }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}
