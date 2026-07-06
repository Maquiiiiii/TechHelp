import { create } from 'zustand';

// Utilidad de aceleración en JavaScript pura para evitar la degradación del rendimiento en eventos de desplazamiento/ratón.
const throttle = (func, limit) => {
  let inThrottle;
  return function(...args) {
    const context = this;
    if (!inThrottle) {
      func.apply(context, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
};

let timeoutId = null;
let cleanupFn = null;

const setupActivityTimeout = (logoutFn, role) => {
  if (timeoutId) clearTimeout(timeoutId);
  if (cleanupFn) {
    cleanupFn();
    cleanupFn = null;
  }
  
  if (role !== 'Tecnico' && role !== 'Administrador') {
    return;
  }

  // Función acelerada para restablecer el temporizador de inactividad de 15 minutos
  const handleActivity = throttle(() => {
    if (timeoutId) clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      console.warn("Sesión cerrada automáticamente por inactividad de 15 minutos.");
      logoutFn();
      window.location.href = '/login';
    }, 15 * 60 * 1000); // exactamente 15 minutos de inactividad
  }, 1000); // máximo una vez por segundo

  // Oyentes de actividad global
  window.addEventListener('mousemove', handleActivity);
  window.addEventListener('keydown', handleActivity);
  window.addEventListener('mousedown', handleActivity);
  window.addEventListener('scroll', handleActivity);

  // Iniciar la cuenta inicial atrás
  if (timeoutId) clearTimeout(timeoutId);
  timeoutId = setTimeout(() => {
    console.warn("Sesión cerrada automáticamente por inactividad de 15 minutos.");
    logoutFn();
    window.location.href = '/login';
  }, 15 * 60 * 1000);

  // Guarde la rutina de limpieza
  cleanupFn = () => {
    if (timeoutId) clearTimeout(timeoutId);
    window.removeEventListener('mousemove', handleActivity);
    window.removeEventListener('keydown', handleActivity);
    window.removeEventListener('mousedown', handleActivity);
    window.removeEventListener('scroll', handleActivity);
  };
};

const getInitialValues = () => {
  const token = localStorage.getItem('token');
  const cuentaBloqueadaLocal = localStorage.getItem('cuentaBloqueada') === 'true';
  if (!token) {
    return {
      user: null,
      role: null,
      organizationRut: null,
      userName: null,
      cuentaBloqueada: cuentaBloqueadaLocal,
    };
  }
  try {
    const payloadPart = token.split('.')[1];
    const decoded = JSON.parse(atob(payloadPart));
    return {
      user: decoded.sub || null,
      role: decoded.role || null,
      organizationRut: decoded.organization_rut || decoded.rut || null,
      userName: decoded.name || null,
      cuentaBloqueada: !!decoded.cuenta_bloqueada || cuentaBloqueadaLocal,
    };
  } catch (e) {
    console.error('Error parsing token on init:', e);
    return {
      user: null,
      role: null,
      organizationRut: null,
      userName: null,
      cuentaBloqueada: cuentaBloqueadaLocal,
    };
  }
};

const initials = getInitialValues();

export const useAuthStore = create((set, get) => ({
  user: initials.user, // Correo electrónico del usuario (asunto)
  token: localStorage.getItem('token') || null,
  role: initials.role,
  isAuthenticated: !!localStorage.getItem('token'),
  especialidad: localStorage.getItem('especialidad') || null,
  requiresPasswordChange: localStorage.getItem('requiresPasswordChange') === 'true',
  organizationRut: initials.organizationRut,
  userName: initials.userName,
  cuentaBloqueada: initials.cuentaBloqueada,
  hasHydrated: true,
  
  setLoginSuccess: (token, role, email) => {
    localStorage.setItem('token', token);
    localStorage.setItem('role', role);
    
    let requiresPasswordChange = false;
    let organizationRut = null;
    let userName = null;
    let cuentaBloqueada = false;
    try {
      const payloadPart = token.split('.')[1];
      const decoded = JSON.parse(atob(payloadPart));
      requiresPasswordChange = !!decoded.requires_password_change;
      organizationRut = decoded.organization_rut || decoded.rut || null;
      userName = decoded.name || null;
      cuentaBloqueada = !!decoded.cuenta_bloqueada;
    } catch (e) {
      console.error('Error decodificando token en authStore:', e);
    }
    
    localStorage.setItem('requiresPasswordChange', String(requiresPasswordChange));
    localStorage.setItem('cuentaBloqueada', String(cuentaBloqueada));
    if (organizationRut) {
      localStorage.setItem('organizationRut', organizationRut);
    } else {
      localStorage.removeItem('organizationRut');
    }
    
    set({
      token,
      role,
      user: email,
      isAuthenticated: true,
      requiresPasswordChange,
      organizationRut,
      userName,
      cuentaBloqueada,
    });
    setupActivityTimeout(get().logout, role);
  },

  setRequiresPasswordChange: (val) => {
    localStorage.setItem('requiresPasswordChange', String(val));
    set({ requiresPasswordChange: !!val });
  },

  setCuentaBloqueada: (val) => {
    localStorage.setItem('cuentaBloqueada', String(val));
    set({ cuentaBloqueada: !!val });
  },

  setEspecialidad: (especialidad) => {
    localStorage.setItem('especialidad', especialidad);
    set({ especialidad });
  },
  
  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('especialidad');
    localStorage.removeItem('requiresPasswordChange');
    localStorage.removeItem('organizationRut');
    localStorage.removeItem('cuentaBloqueada');
    if (timeoutId) clearTimeout(timeoutId);
    if (cleanupFn) {
      cleanupFn();
      cleanupFn = null;
    }
    set({
      token: null,
      role: null,
      user: null,
      isAuthenticated: false,
      especialidad: null,
      requiresPasswordChange: false,
      organizationRut: null,
      userName: null,
      cuentaBloqueada: false,
    });
  }

}));

// Inicialice el tiempo de espera al iniciar la aplicación si ya está autenticado y el rol coincide
const initialRole = localStorage.getItem('role');
if (initialRole && (initialRole === 'Tecnico' || initialRole === 'Administrador')) {
  setTimeout(() => {
    const store = useAuthStore.getState();
    if (store.isAuthenticated) {
      setupActivityTimeout(store.logout, initialRole);
    }
  }, 100);
}

export default useAuthStore;