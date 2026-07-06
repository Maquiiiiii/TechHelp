import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const ProtectedRoute = ({ children, allowedRoles }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const role = useAuthStore((state) => state.role);
  const requiresPasswordChange = useAuthStore((state) => state.requiresPasswordChange);
  const cuentaBloqueada = useAuthStore((state) => state.cuentaBloqueada);
  const hasHydrated = useAuthStore((state) => state.hasHydrated);
  const location = useLocation();

  if (!hasHydrated) {
    return (
      <div className="flex flex-col items-center justify-center w-full h-64 gap-3 bg-[#1A1D20]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
        <span className="text-sm tracking-wider text-white/40">Iniciando sesión...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // 1. Verificación de cuenta bloqueada
  if (role === 'Cliente' && cuentaBloqueada && location.pathname !== '/blocked') {
    return <Navigate to="/blocked" replace />;
  }

  // 2. Forzar la verificación de cambio de contraseña
  if (role === 'Tecnico' && requiresPasswordChange && location.pathname !== '/force-password-change') {
    return <Navigate to="/force-password-change" replace />;
  }

  // 2. Evite el acceso a /force-password-change si no es necesario
  if (location.pathname === '/force-password-change' && (!requiresPasswordChange || role !== 'Tecnico')) {
    if (role === 'Tecnico') {
      return <Navigate to="/tickets" replace />;
    }
    return <Navigate to="/" replace />;
  }

  if (allowedRoles && (!role || !allowedRoles.includes(role))) {
    // Si no está autorizado, redirige a su página de inicio predeterminada según su función.
    if (role === 'Tecnico') {
      return <Navigate to="/tickets/all" replace />;
    } else if (role === 'Cliente') {
      return <Navigate to="/tickets" replace />;
    }
    return <Navigate to="/login" replace />;
  }

  // Admita el uso directo de contenedores secundarios y el enrutamiento Anidamiento de salidas
  return children ? children : <Outlet />;
};


export default ProtectedRoute;