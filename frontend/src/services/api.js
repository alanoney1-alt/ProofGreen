import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

// Auth API
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
  updatePassword: (data) => api.put('/auth/password', data),
  getVerticals: () => api.get('/auth/verticals')
}

// Jobs API
export const jobsAPI = {
  list: (params) => api.get('/jobs', { params }),
  get: (id) => api.get(`/jobs/${id}`),
  create: (data) => api.post('/jobs', data),
  update: (id, data) => api.put(`/jobs/${id}`, data),
  uploadPhotos: (id, formData) => api.post(`/jobs/${id}/photos`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  addItems: (id, items) => api.post(`/jobs/${id}/items`, { items }),
  deleteItem: (jobId, itemId) => api.delete(`/jobs/${jobId}/items/${itemId}`)
}

// Agent API
export const agentAPI = {
  process: (formData) => api.post('/agent/process', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  analyzePhoto: (formData) => api.post('/agent/analyze-photo', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  getStatus: (jobId) => api.get(`/agent/status/${jobId}`),
  getExecutions: (params) => api.get('/agent/executions', { params })
}

// Metrics API
export const metricsAPI = {
  dashboard: () => api.get('/metrics/dashboard'),
  trends: (params) => api.get('/metrics/trends', { params }),
  byCategory: () => api.get('/metrics/by-category'),
  leaderboard: () => api.get('/metrics/leaderboard'),
  milestones: () => api.get('/metrics/milestones')
}

// Reports API
export const reportsAPI = {
  list: (params) => api.get('/reports', { params }),
  get: (id) => api.get(`/reports/${id}`),
  getPublic: (token) => api.get(`/reports/public/${token}`),
  generateJob: (jobId) => api.post(`/reports/generate/job/${jobId}`),
  generatePeriod: (data) => api.post('/reports/generate/period', data),
  share: (id, isPublic) => api.put(`/reports/${id}/share`, { isPublic }),
  delete: (id) => api.delete(`/reports/${id}`)
}

// Subscriptions API
export const subscriptionsAPI = {
  getPlans: () => api.get('/subscriptions/plans'),
  getCurrent: () => api.get('/subscriptions/current'),
  upgrade: (data) => api.post('/subscriptions/upgrade', data),
  cancel: () => api.post('/subscriptions/cancel'),
  getHistory: () => api.get('/subscriptions/history')
}

// Companies API
export const companiesAPI = {
  get: (id) => api.get(`/companies/${id}`),
  update: (id, data) => api.put(`/companies/${id}`, data),
  updateVerticals: (id, verticals) => api.put(`/companies/${id}/verticals`, { verticals }),
  getUsers: (id) => api.get(`/companies/${id}/users`),
  addUser: (id, data) => api.post(`/companies/${id}/users`, data)
}
