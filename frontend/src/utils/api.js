import axios from 'axios';

// Crear una instancia de Axios con el backend API raíz
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, // Límite de tiempo de espera de 10 segundos
});

// Interceptor de solicitudes: adjunte el token de autenticación si está disponible
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

// Interceptor de respuesta: detecta excepciones de código de estado HTTP global
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Manejar la caducidad de la autenticación (401)
    if (error.response && error.response.status === 401) {
      console.warn('Sesión expirada. Redireccionando a Login.');
      localStorage.removeItem('token');
      localStorage.removeItem('role');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    if (error.response && error.response.status === 403) {
      const detail = error.response.data?.detail || '';
      if (detail.includes('Cuenta bloqueada') || detail.includes('desactivada')) {
        console.warn('Organización desactivada. Redireccionando a Bloqueo.');
        localStorage.setItem('cuentaBloqueada', 'true');
        window.location.href = '/blocked';
      }
    }
    return Promise.reject(error);
  }
);

export default api;