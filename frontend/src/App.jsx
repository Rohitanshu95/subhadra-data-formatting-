import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import NewBatch from './pages/NewBatch';
import BatchMonitor from './pages/BatchMonitor';
import BatchResults from './pages/BatchResults';
import LogsPage from './pages/LogsPage';
import ParsedRecordsPage from './pages/ParsedRecordsPage';

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <Navbar />
        <main style={{ flex: 1 }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/batches/new" element={<NewBatch />} />
            <Route path="/batches/:id" element={<BatchMonitor />} />
            <Route path="/batches/:id/records" element={<ParsedRecordsPage />} />
            <Route path="/batches/:id/results" element={<BatchResults />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
