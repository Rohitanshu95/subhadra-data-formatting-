import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Layers, PlusCircle, LayoutDashboard, Database, ShieldCheck, CheckCircle2, FileText } from 'lucide-react';

export default function Navbar() {
  const location = useLocation();
  const isActive = (path) => location.pathname === path;

  return (
    <header style={{ boxShadow: '0 2px 4px rgba(0,0,0,0.06)' }}>
      {/* Official Top Flag Accent Bar */}
      <div className="gov-flag-bar" />

      {/* Official Portal Header */}
      <div style={{
        backgroundColor: '#0f2744',
        color: '#ffffff',
        borderBottom: '1px solid #091b30',
      }}>
        <div style={{
          width: '100%',
          maxWidth: '100%',
          padding: '0 24px',
          height: '66px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          {/* Brand & Portal Identity */}
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '4px',
              background: '#1d4ed8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid rgba(255, 255, 255, 0.2)',
            }}>
              <Database size={20} color="#ffffff" />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: '1.15rem', letterSpacing: '-0.01em', color: '#ffffff' }}>
                APBS Processing Portal
              </div>
              <div style={{ fontSize: '0.725rem', color: '#93c5fd', fontWeight: 500, letterSpacing: '0.02em' }}>
                177-CHAR FIXED-WIDTH VALIDATION & DEDUPLICATION SYSTEM
              </div>
            </div>
          </Link>

          {/* Navigation links */}
          <nav style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Link
              to="/"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: '4px',
                fontSize: '0.875rem',
                fontWeight: 600,
                color: isActive('/') ? '#ffffff' : '#cbd5e1',
                background: isActive('/') ? 'rgba(255, 255, 255, 0.15)' : 'transparent',
                transition: 'all 0.15s ease',
              }}
            >
              <LayoutDashboard size={16} />
              Dashboard
            </Link>

            <Link
              to="/logs"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                borderRadius: '4px',
                fontSize: '0.875rem',
                fontWeight: 600,
                color: isActive('/logs') ? '#ffffff' : '#cbd5e1',
                background: isActive('/logs') ? 'rgba(255, 255, 255, 0.15)' : 'transparent',
                transition: 'all 0.15s ease',
              }}
            >
              <FileText size={16} />
              Logs
            </Link>

            <Link
              to="/batches/new"
              className="btn btn-primary"
              style={{ padding: '8px 16px', fontSize: '0.875rem', background: '#2563eb', border: '1px solid #3b82f6' }}
            >
              <PlusCircle size={16} />
              Upload Batch
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}
