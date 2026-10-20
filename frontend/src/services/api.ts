import axios from 'axios';

// IMPORTANTE: no se fija "Content-Type" por defecto. Un valor fijo de
// application/json hace que axios serialice como JSON las peticiones
// multipart (FormData) y un "multipart/form-data" sin boundary rompe el
// parseo del cuerpo en el backend ("Missing boundary in multipart").
// Axios aplica application/json automáticamente a los payloads de objeto.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
});

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

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
