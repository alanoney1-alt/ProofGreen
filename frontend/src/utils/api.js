import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Handle specific status codes
      switch (error.response.status) {
        case 401:
          // Unauthorized - clear token and redirect to login
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          localStorage.removeItem('company');
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
          break;
        case 403:
          // Forbidden - user doesn't have permission
          console.error('Access forbidden:', error.response.data);
          break;
        case 404:
          // Not found
          console.error('Resource not found:', error.response.data);
          break;
        case 429:
          // Rate limited
          console.error('Rate limited:', error.response.data);
          break;
        case 500:
          // Server error
          console.error('Server error:', error.response.data);
          break;
        default:
          console.error('API error:', error.response.data);
      }
    } else if (error.request) {
      // Network error
      console.error('Network error - no response received');
    } else {
      console.error('Request error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default api;

// Convenience methods for common operations
export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (data) => api.post('/auth/register', data),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  refreshToken: () => api.post('/auth/refresh')
};

export const jobsApi = {
  list: (params) => api.get('/jobs', { params }),
  get: (id) => api.get(`/jobs/${id}`),
  create: (data) => api.post('/jobs', data),
  update: (id, data) => api.put(`/jobs/${id}`, data),
  delete: (id) => api.delete(`/jobs/${id}`),
  uploadPhotos: (id, formData) => api.post(`/jobs/${id}/photos`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  addItems: (id, items) => api.post(`/jobs/${id}/items`, { items }),
  deleteItem: (jobId, itemId) => api.delete(`/jobs/${jobId}/items/${itemId}`),
  getVerticals: () => api.get('/jobs/verticals')
};

export const complianceApi = {
  getStatus: () => api.get('/compliance/status'),
  getRequirements: (verticalId) => api.get(`/compliance/requirements/${verticalId}`),
  checkReadiness: (contractType, verticalId) =>
    api.post('/compliance/check-readiness', { contractType, verticalId }),
  getReport: (params) => api.get('/compliance/report', { params }),
  getJobScore: (jobId) => api.get(`/compliance/score/${jobId}`),
  submitEsgData: (jobId, verticalSlug, formData) =>
    api.post('/compliance/esg-data', { jobId, verticalSlug, formData }),
  getFormFields: (verticalSlug) => api.get(`/compliance/form-fields/${verticalSlug}`),
  updateRequirement: (requirementId, data) =>
    api.put(`/compliance/requirement/${requirementId}`, data),
  addCertification: (data) => api.post('/compliance/certification', data),
  getCertifications: (params) => api.get('/compliance/certifications', { params }),
  deleteCertification: (id) => api.delete(`/compliance/certification/${id}`),
  getAnalytics: (period) => api.get('/compliance/analytics', { params: { period } })
};

export const documentsApi = {
  upload: (formData) => api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  getByJob: (jobId) => api.get(`/documents/job/${jobId}`),
  getByCompany: (params) => api.get('/documents/company', { params }),
  get: (id) => api.get(`/documents/${id}`),
  update: (id, data) => api.put(`/documents/${id}`, data),
  verify: (id, notes) => api.put(`/documents/${id}/verify`, { notes }),
  delete: (id) => api.delete(`/documents/${id}`),
  getTypes: () => api.get('/documents/meta/types')
};

export const reportsApi = {
  list: (params) => api.get('/reports', { params }),
  get: (id) => api.get(`/reports/${id}`),
  getPublic: (token) => api.get(`/reports/public/${token}`),
  generate: (jobId) => api.post(`/reports/generate/${jobId}`),
  downloadPdf: (id) => api.get(`/reports/${id}/pdf`, { responseType: 'blob' }),
  downloadCompliancePdf: () => api.get('/reports/compliance/pdf', { responseType: 'blob' })
};

export const metricsApi = {
  getDashboard: (params) => api.get('/metrics/dashboard', { params }),
  getOverview: () => api.get('/metrics/overview'),
  getByCategory: () => api.get('/metrics/by-category'),
  getTrends: (period) => api.get('/metrics/trends', { params: { period } })
};

export const agentApi = {
  process: (jobId, formData) => api.post('/agent/process', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  analyzePhoto: (formData) => api.post('/agent/analyze-photo', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  identifyJobType: (items, jobId) => api.post('/agent/identify-job-type', { items, jobId }),
  calculateCarbon: (jobId, items) => api.post('/agent/calculate-carbon', { jobId, items }),
  checkMilestones: (jobId) => api.post('/agent/check-milestones', { jobId }),
  generateReport: (jobId) => api.post('/agent/generate-report', { jobId }),
  checkEsgCompliance: (jobId) => api.post('/agent/check-esg-compliance', { jobId }),
  getExecutions: (params) => api.get('/agent/executions', { params }),
  getStatus: (jobId) => api.get(`/agent/status/${jobId}`)
};

export const subscriptionApi = {
  getPlans: () => api.get('/subscriptions/plans'),
  getCurrent: () => api.get('/subscriptions/current'),
  createCheckout: (planId) => api.post('/subscriptions/checkout', { planId }),
  createPortal: () => api.post('/subscriptions/portal'),
  cancel: () => api.post('/subscriptions/cancel')
};
