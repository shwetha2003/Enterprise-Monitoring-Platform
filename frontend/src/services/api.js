import axios from 'axios';
import { jwtDecode } from 'jwt-decode';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If error is 401 and we haven't tried refreshing yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token } = response.data;
          localStorage.setItem('access_token', access_token);
          if (refresh_token) {
            localStorage.setItem('refresh_token', refresh_token);
          }

          // Retry the original request
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return axios(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, logout user
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// Auth methods
export const auth = {
  login: async (username, password) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const response = await axios.post(`${API_BASE_URL}/auth/login`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    const { access_token, user } = response.data;
    
    // Store tokens and user info
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('user', JSON.stringify(user));
    
    return response.data;
  },

  register: async (userData) => {
    const response = await api.post('/auth/register', userData);
    return response.data;
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  },

  getCurrentUser: () => {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
  },

  isAuthenticated: () => {
    const token = localStorage.getItem('access_token');
    if (!token) return false;

    try {
      const decoded = jwtDecode(token);
      const currentTime = Date.now() / 1000;
      return decoded.exp > currentTime;
    } catch (error) {
      return false;
    }
  },

  hasRole: (role) => {
    const user = auth.getCurrentUser();
    return user && (user.role === role || user.role === 'admin');
  },
};

// Asset methods
export const assets = {
  getAll: (params = {}) => api.get('/assets', { params }),
  getById: (id) => api.get(`/assets/${id}`),
  create: (data) => api.post('/assets', data),
  update: (id, data) => api.put(`/assets/${id}`, data),
  delete: (id) => api.delete(`/assets/${id}`),
  getMetrics: (id, params = {}) => api.get(`/assets/${id}/metrics`, { params }),
  getPerformance: (id) => api.get(`/assets/${id}/performance`),
  simulateData: (id, duration = 24, interval = 5) => 
    api.post(`/assets/${id}/simulate`, { duration_hours: duration, interval_minutes: interval }),
};

// Alert methods
export const alerts = {
  getAll: (params = {}) => api.get('/alerts', { params }),
  getById: (id) => api.get(`/alerts/${id}`),
  create: (data) => api.post('/alerts', data),
  update: (id, data) => api.put(`/alerts/${id}`, data),
  delete: (id) => api.delete(`/alerts/${id}`),
  getSummary: (days = 7) => api.get(`/alerts/stats/summary?days=${days}`),
  acknowledgeMultiple: (alertIds) => api.post('/alerts/bulk/acknowledge', { alert_ids: alertIds }),
};

// Monitoring methods
export const monitoring = {
  getHealthOverview: () => api.get('/monitoring/health/overview'),
  getRealtimeMetrics: (params = {}) => api.get('/monitoring/metrics/realtime', { params }),
  getPredictiveMaintenance: (days = 7) => api.get(`/monitoring/predictive/maintenance?days_ahead=${days}`),
  getAssetTrends: (assetId, metricType, period = '24h') => 
    api.get(`/monitoring/trends/${assetId}?metric_type=${metricType}&period=${period}`),
  simulateWebhookData: (assetCount = 10, metricCount = 100) =>
    api.post('/monitoring/webhook/simulate', { asset_count: assetCount, metric_count: metricCount }),
};

// Dashboard methods
export const dashboard = {
  getStats: () => api.get('/dashboard/stats'),
  getTopPerformance: (limit = 10) => api.get(`/dashboard/performance/top?limit=${limit}`),
  getRecentActivity: (limit = 20) => api.get(`/dashboard/activity/recent?limit=${limit}`),
  getPredictions: () => api.get('/dashboard/predictions/overview'),
  getGeographicData: () => api.get('/dashboard/geographic/overview'),
};

// Report methods
export const reports = {
  getAll: (params = {}) => api.get('/reports', { params }),
  getById: (id) => api.get(`/reports/${id}`),
  create: (data) => api.post('/reports', data),
  update: (id, data) => api.put(`/reports/${id}`, data),
  delete: (id) => api.delete(`/reports/${id}`),
  generate: (id) => api.post(`/reports/${id}/generate`),
  download: (id) => api.get(`/reports/${id}/download`, { responseType: 'blob' }),
};

export { api };
