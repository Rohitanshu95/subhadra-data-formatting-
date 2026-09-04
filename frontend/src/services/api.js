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

export const listBatches = async (refresh = false) => {
  const res = await api.get('/batches', { params: refresh ? { refresh: true } : {} });
  return res.data;
};

export const getOverviewStats = async (refresh = false) => {
  const res = await api.get('/batches/overview/stats', { params: refresh ? { refresh: true } : {} });
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

export const getImportProgress = async (batchId) => {
  const res = await api.get(`/batches/${batchId}/import-progress`);
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
   * Download all records in CSV format via native stream download.
   * When batchId is 'all', downloads ALL data present in the MySQL database.
   */
  try {
    const queryParams = new URLSearchParams();
    if (params.success_flag !== undefined && params.success_flag !== '') queryParams.append('success_flag', params.success_flag);
    if (params.reason_code !== undefined && params.reason_code !== '') queryParams.append('reason_code', params.reason_code);
    if (params.status !== undefined && params.status !== '' && params.status !== 'ALL') queryParams.append('status', params.status);
    if (params.search !== undefined && params.search !== '') queryParams.append('search', params.search);

    const queryStr = queryParams.toString() ? `?${queryParams.toString()}` : '';
    const target = (!batchId || batchId.toLowerCase() === 'all') ? 'all' : batchId;
    const downloadUrl = `/api/batches/${target}/download/records/csv${queryStr}`;

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.setAttribute('download', `${target === 'all' ? 'complete_database' : target}_records.csv`);
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      if (link.parentNode) {
        document.body.removeChild(link);
      }
    }, 200);
  } catch (error) {
    console.error('Failed to download CSV:', error);
    throw error;
  }
};

export const downloadRecordsAsText = async (batchId, params = {}) => {
  /**
   * Download all records in pipe-delimited text format via native stream download.
   * When batchId is 'all', downloads ALL data present in the MySQL database.
   */
  try {
    const queryParams = new URLSearchParams();
    if (params.success_flag !== undefined && params.success_flag !== '') queryParams.append('success_flag', params.success_flag);
    if (params.reason_code !== undefined && params.reason_code !== '') queryParams.append('reason_code', params.reason_code);
    if (params.status !== undefined && params.status !== '' && params.status !== 'ALL') queryParams.append('status', params.status);
    if (params.search !== undefined && params.search !== '') queryParams.append('search', params.search);

    const queryStr = queryParams.toString() ? `?${queryParams.toString()}` : '';
    const target = (!batchId || batchId.toLowerCase() === 'all') ? 'all' : batchId;
    const downloadUrl = `/api/batches/${target}/download/records/text${queryStr}`;

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.setAttribute('download', `${target === 'all' ? 'complete_database' : target}_records.txt`);
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      if (link.parentNode) {
        document.body.removeChild(link);
      }
    }, 200);
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


