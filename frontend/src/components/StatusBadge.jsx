import React from 'react';
import { 
  Clock, 
  Loader2, 
  CheckCircle, 
  AlertTriangle, 
  Copy, 
  ShieldCheck, 
  Database, 
  XCircle 
} from 'lucide-react';

export default function StatusBadge({ status }) {
  const normStatus = (status || 'READY').toUpperCase();

  const getBadgeConfig = () => {
    switch (normStatus) {
      case 'READY':
        return { className: 'badge-ready', icon: Clock, label: 'Ready' };
      case 'UPLOADING':
        return { className: 'badge-processing', icon: Loader2, label: 'Uploading' };
      case 'QUEUED':
        return { className: 'badge-ready', icon: Clock, label: 'Queued' };
      case 'PROCESSING':
        return { className: 'badge-processing', icon: Loader2, label: 'Processing' };
      case 'COMPLETED':
        return { className: 'badge-completed', icon: CheckCircle, label: 'Completed' };
      case 'COMPLETED_WITH_ERRORS':
        return { className: 'badge-completed_with_errors', icon: AlertTriangle, label: 'Completed (Errors)' };
      case 'DUPLICATE_FILE':
        return { className: 'badge-duplicate_file', icon: Copy, label: 'Duplicate File' };
      case 'AWAITING_VERIFICATION':
        return { className: 'badge-verified', icon: ShieldCheck, label: 'Awaiting Verification' };
      case 'VERIFIED':
        return { className: 'badge-verified', icon: ShieldCheck, label: 'Verified' };
      case 'IMPORTING':
        return { className: 'badge-processing', icon: Loader2, label: 'Importing to SQL' };
      case 'IMPORTED':
        return { className: 'badge-imported', icon: Database, label: 'Imported to SQL' };
      case 'FAILED':
        return { className: 'badge-failed', icon: XCircle, label: 'Failed' };
      default:
        return { className: 'badge-ready', icon: Clock, label: normStatus };
    }
  };

  const { className, icon: Icon, label } = getBadgeConfig();

  return (
    <span className={`badge ${className}`}>
      <Icon size={12} className={normStatus === 'PROCESSING' || normStatus === 'UPLOADING' ? 'animate-spin' : ''} />
      {label}
    </span>
  );
}
