import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  Database,
  FileCheck2,
  Layers,
  ShieldCheck,
  Zap,
  HardDrive,
  FileText,
  PlusCircle,
  BarChart3,
  CheckCircle2,
  Sparkles,
  Server,
  Lock,
  RefreshCw,
  FolderTree,
  AlertTriangle
} from 'lucide-react';

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="landing-page-wrapper">
      {/* ── Hero Section ── */}
      <section className="landing-hero">
        <div className="landing-hero-backdrop" />
        <div className="landing-container landing-hero-content">
          <div className="landing-badge">
            <span className="landing-badge-pulse" />
            <ShieldCheck size={15} className="landing-badge-icon" />
            <span>Subhadra APBS Core Engine • Production v1.0</span>
          </div>

          <h1 className="landing-hero-title">
            177-Character Fixed-Width <br />
            <span className="landing-hero-gradient">Data Validation & Deduplication</span> Portal
          </h1>

          <p className="landing-hero-description">
            High-throughput enterprise streaming platform engineered for Direct Benefit Transfer (DBT) and
            Aadhaar Payment Bridge System (APBS) records. Real-time length enforcement, SHA-256 content hashing,
            and automated error segregation at scale.
          </p>

          <div className="landing-cta-group">
            <button
              id="btn-proceed-dashboard"
              onClick={() => navigate('/dashboard')}
              className="btn btn-landing-primary"
            >
              <span>Proceed to Dashboard</span>
              <ArrowRight size={18} />
            </button>

            <button
              id="btn-landing-upload"
              onClick={() => navigate('/batches/new')}
              className="btn btn-landing-secondary"
            >
              <PlusCircle size={18} />
              <span>Upload New Batch</span>
            </button>

            <button
              id="btn-landing-logs"
              onClick={() => navigate('/logs')}
              className="btn btn-landing-outline"
            >
              <FileText size={18} />
              <span>Audit Logs</span>
            </button>
          </div>

          {/* Quick Metrics Strip */}
          <div className="landing-stats-grid">
            <div className="landing-stat-card">
              <div className="landing-stat-number">177</div>
              <div className="landing-stat-label">Characters / Record Fixed-Width</div>
            </div>
            <div className="landing-stat-card">
              <div className="landing-stat-number">17</div>
              <div className="landing-stat-label">Standard Field Validations</div>
            </div>
            <div className="landing-stat-card">
              <div className="landing-stat-number">SHA-256</div>
              <div className="landing-stat-label">Cryptographic Deduplication</div>
            </div>
            <div className="landing-stat-card">
              <div className="landing-stat-number">&lt; 50 MB</div>
              <div className="landing-stat-label">Constant Low Memory Stream</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Core Capabilities ── */}
      <section className="landing-section">
        <div className="landing-container">
          <div className="landing-section-header">
            <div className="landing-section-tag">System Capabilities</div>
            <h2 className="landing-section-title">Built for Mission-Critical Payment File Processing</h2>
            <p className="landing-section-subtitle">
              Engineered to process massive financial settlement files without memory bottlenecks or duplicate disbursements.
            </p>
          </div>

          <div className="landing-features-grid">
            <div className="landing-feature-card">
              <div className="landing-feature-icon-box bg-blue">
                <FileCheck2 size={24} color="#1d4ed8" />
              </div>
              <h3 className="landing-feature-title">Strict 177-Char Parsing</h3>
              <p className="landing-feature-text">
                Byte-precise line length verification, non-credit header/trailer separation (record code 33), and automated error record isolation.
              </p>
              <div className="landing-feature-tags">
                <span>Offset Tables</span>
                <span>Type Checking</span>
                <span>Zero Truncation</span>
              </div>
            </div>

            <div className="landing-feature-card">
              <div className="landing-feature-icon-box bg-green">
                <ShieldCheck size={24} color="#15803d" />
              </div>
              <h3 className="landing-feature-title">SHA-256 Deduplication</h3>
              <p className="landing-feature-text">
                Single-pass on-the-fly content hashing prevents redundant re-processing of duplicate files regardless of renaming.
              </p>
              <div className="landing-feature-tags">
                <span>File Hashing</span>
                <span>Record Hashing</span>
                <span>Zero Double-Credits</span>
              </div>
            </div>

            <div className="landing-feature-card">
              <div className="landing-feature-icon-box bg-purple">
                <Zap size={24} color="#7e22ce" />
              </div>
              <h3 className="landing-feature-title">Streaming Queue Engine</h3>
              <p className="landing-feature-text">
                Processes gigabyte-scale APBS files using buffered chunk streams with persistent background task workers and live progress feeds.
              </p>
              <div className="landing-feature-tags">
                <span>Low Memory</span>
                <span>Background Queue</span>
                <span>Live Socket / Polling</span>
              </div>
            </div>

            <div className="landing-feature-card">
              <div className="landing-feature-icon-box bg-amber">
                <BarChart3 size={24} color="#b45309" />
              </div>
              <h3 className="landing-feature-title">Live Analytics & Exports</h3>
              <p className="landing-feature-text">
                Interactive dashboards with valid/invalid record counters, error distribution charts, and one-click clean file downloads.
              </p>
              <div className="landing-feature-tags">
                <span>Export Clean .txt</span>
                <span>Error Reports</span>
                <span>Audit Logs</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Processing Pipeline Workflow ── */}
      <section className="landing-section landing-section-alt">
        <div className="landing-container">
          <div className="landing-section-header">
            <div className="landing-section-tag">Architecture & Flow</div>
            <h2 className="landing-section-title">End-to-End Ingestion Pipeline</h2>
            <p className="landing-section-subtitle">
              How incoming APBS data is streamed, validated, filtered, and certified.
            </p>
          </div>

          <div className="landing-workflow-grid">
            <div className="landing-step-card">
              <div className="landing-step-badge">1</div>
              <div className="landing-step-icon">
                <HardDrive size={22} color="#0f2744" />
              </div>
              <h4>Batch Ingestion</h4>
              <p>Multi-file chunked upload with filename sanitization and directory structuring.</p>
            </div>

            <div className="landing-step-arrow">➔</div>

            <div className="landing-step-card">
              <div className="landing-step-badge">2</div>
              <div className="landing-step-icon">
                <RefreshCw size={22} color="#1d4ed8" />
              </div>
              <h4>Length & Header Scan</h4>
              <p>Strict 177-char line checks, header identification, and invalid record filtering.</p>
            </div>

            <div className="landing-step-arrow">➔</div>

            <div className="landing-step-card">
              <div className="landing-step-badge">3</div>
              <div className="landing-step-icon">
                <Lock size={22} color="#15803d" />
              </div>
              <h4>Deduplication Check</h4>
              <p>Content hash comparison against historical index to catch exact or modified duplicates.</p>
            </div>

            <div className="landing-step-arrow">➔</div>

            <div className="landing-step-card">
              <div className="landing-step-badge">4</div>
              <div className="landing-step-icon">
                <Database size={22} color="#b45309" />
              </div>
              <h4>DB Sync & Clean Export</h4>
              <p>Validated records ingested into database; clean & error output files streamed to storage.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Quick Portal Actions ── */}
      <section className="landing-section">
        <div className="landing-container">
          <div className="landing-action-banner">
            <div className="landing-action-text">
              <h2>Ready to monitor or process APBS batches?</h2>
              <p>Access the operational dashboard to view active batches, monitor streaming queues, and inspect audit logs.</p>
            </div>
            <div className="landing-action-btns">
              <button
                id="btn-bottom-dashboard"
                onClick={() => navigate('/dashboard')}
                className="btn btn-landing-primary"
                style={{ fontSize: '1rem', padding: '14px 28px' }}
              >
                <span>Proceed to Dashboard</span>
                <ArrowRight size={20} />
              </button>
              <button
                id="btn-bottom-upload"
                onClick={() => navigate('/batches/new')}
                className="btn btn-landing-secondary"
                style={{ fontSize: '1rem', padding: '14px 24px' }}
              >
                <PlusCircle size={20} />
                <span>Upload Batch</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Official Footer ── */}
      <footer className="landing-footer">
        <div className="landing-container landing-footer-content">
          <div className="landing-footer-brand">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div className="landing-footer-logo">
                <Database size={18} color="#ffffff" />
              </div>
              <div>
                <div style={{ fontWeight: 800, color: '#ffffff', fontSize: '0.95rem' }}>
                  APBS Data Processing Portal
                </div>
                <div style={{ fontSize: '0.75rem', color: '#93c5fd' }}>
                  Subhadra Financial Data Reconciliation Engine
                </div>
              </div>
            </div>
          </div>

          <div className="landing-footer-links">
            <button onClick={() => navigate('/dashboard')} className="footer-link-btn">Dashboard</button>
            <button onClick={() => navigate('/batches/new')} className="footer-link-btn">New Batch</button>
            <button onClick={() => navigate('/logs')} className="footer-link-btn">System Logs</button>
          </div>

          <div className="landing-footer-meta">
            <span>© 2026 APBS Processing Portal. Secure Fixed-Width System.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
