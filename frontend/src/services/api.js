import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const createBatch = async () => {
  const res = await api.post('/batches');
  return res.data;
};

export const listBatches = async () => {
  const res = await api.get('/batches');
  return res.data;
};

export const getOverviewStats = async () => {
  const res = await api.get('/batches/overview/stats');
  return res.data;
};

export const getBatch = async (batchId) => {
  const res = await api.get(`/batches/${batchId}`);
  return res.data;
};

export const getBatchFiles = async (batchId) => {
  const res = await api.get(`/batches/${batchId}/files`);
  return res.data;
};

export const getBatchProgress = async (batchId) => {
  const res = await api.get(`/batches/${batchId}/progress`);
  return res.data;
};

export const uploadBatchFiles = async (batchId, files) => {
  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
  }
  const res = await api.post(`/batches/${batchId}/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return res.data;
};

export const processBatch = async (batchId) => {
  const res = await api.post(`/batches/${batchId}/process`);
  return res.data;
};

export const verifyBatch = async (batchId) => {
  const res = await api.post(`/batches/${batchId}/verify`);
  return res.data;
};

export const previewCleanRecords = async (batchId, limit = 20) => {
  const res = await api.get(`/batches/${batchId}/preview/clean?limit=${limit}`);
  return res.data;
};

export const previewErrorRecords = async (batchId, limit = 20) => {
  const res = await api.get(`/batches/${batchId}/preview/errors?limit=${limit}`);
  return res.data;
};

export const getBatchSummaryText = async (batchId) => {
  const res = await api.get(`/batches/${batchId}/summary`);
  return res.data;
};

export const importBatchToSql = async (batchId) => {
  const res = await api.post(`/batches/${batchId}/import`);
  return res.data;
};

export const getLogs = async (params = {}) => {
  const res = await api.get('/logs', { params });
  return res.data;
};

export const getParsedRecords = async (batchId, params = {}) => {
  const res = await api.get(`/batches/${batchId}/records`, { params });
  return res.data;
};

export const downloadRecordsAsCSV = async (batchId, params = {}) => {
  /**
   * Download all parsed records (as shown in dashboard) in CSV format
   * Returns a file download in the browser
   * 
   * Optional params:
   * - success_flag: Filter by success flag
   * - reason_code: Filter by reason code
   * - status: Filter by status (COMMITTED, INVALID, etc.)
   * - search: Full-text search
   */
  try {
    const response = await api.get(`/batches/${batchId}/download/records/csv`, { 
      params,
      responseType: 'blob'
    });
    
    // Trigger download
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${batchId}_records.csv`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Failed to download CSV:', error);
    throw error;
  }
};

export const downloadRecordsAsText = async (batchId, params = {}) => {
  /**
   * Download all parsed records (as shown in dashboard) in pipe-delimited text format
   * Returns a file download in the browser
   * 
   * Optional params:
   * - success_flag: Filter by success flag
   * - reason_code: Filter by reason code
   * - status: Filter by status (COMMITTED, INVALID, etc.)
   * - search: Full-text search
   */
  try {
    const response = await api.get(`/batches/${batchId}/download/records/text`, { 
      params,
      responseType: 'blob'
    });
    
    // Trigger download
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${batchId}_records.txt`);
    document.body.appendChild(link);
    link.click();
    link.parentNode.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Failed to download text:', error);
    throw error;
  }
};

export const deleteBatch = async (batchId) => {
  const res = await api.delete(`/batches/${batchId}`);
  return res.data;
};

export const deleteRecord = async (recordId, params = {}) => {
  const res = await api.delete(`/batches/records/${recordId}`, { params });
  return res.data;
};

export default api;


