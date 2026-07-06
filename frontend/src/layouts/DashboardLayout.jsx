import React, { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { 
  Ticket, 
  PlusCircle, 
  Inbox, 
  List, 
  Building, 
  Users, 
  Shield, 
  LogOut,
  User,
  WifiOff,
  Home,
  Globe
} from 'lucide-react';

const DashboardLayout = () => {
  const navigate = useNavigate();
  const { user, role, logout, userName } = useAuthStore();

  // Estado del estado de la conexión de red
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    // Si el técnico o cliente llega a / index, redirige a su página principal (Vista Inicial por Defecto)
    if (window.location.pathname === '/') {
      if (role === 'Tecnico') {
        navigate('/tickets/all');
      } else if (role === 'Cliente') {
        navigate('/tickets');
      }
    }
  }, [role, navigate]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Clases de estilo de estado activo de NavLink (Estilo de cápsula con fondo azul semi-transparente)
  const navLinkClass = ({ isActive }) =>
    `relative flex items-center justify-between px-4 py-3 rounded-lg transition-all duration-200 text-sm font-medium overflow-hidden ${
      isActive
        ? 'text-blue-400 bg-blue-500/10'
        : 'text-zinc-400 hover:text-white hover:bg-white/5'
    }`;

  // Configuraciones de navegación visual de RBAC basadas en los requisitos especificados
  const getNavItems = () => {
    switch (role) {
      case 'Cliente':
        return [
          { path: '/tickets/new', name: 'Crear Ticket', icon: PlusCircle, end: true },
          { path: '/tickets', name: 'Mis Tickets', icon: Ticket, end: true },
        ];
      case 'Tecnico':
        return [
          { path: '/tickets/all', name: 'Todos los Tickets', icon: List, end: false },
          { path: '/tickets/assigned', name: 'Mis Tickets Asignados', icon: Inbox, end: false },
        ];
      case 'Administrador':
        return [
          { path: '/', name: 'Dashboard', icon: Home, end: true },
          { path: '/organizations', name: 'Organizaciones', icon: Building, end: false },
          { path: '/technicians', name: 'Técnicos', icon: Users, end: false },
          { path: '/audit', name: 'Auditoría', icon: Shield, end: false },
        ];
      default:
        return [];
    }
  };

  const navItems = getNavItems();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#1A1D20] text-white/90 font-sans">
      
      {/* Barra lateral: fijada a pantalla con diseño corporativo en azul. */}
      <aside className="fixed top-0 left-0 h-screen w-64 bg-[#14171a] flex flex-col justify-between z-50 rounded-none shadow-2xl transition-all duration-300">
        
        <div className="flex flex-col flex-1 min-h-0">
          {/* Contenedor del logotipo de la marca. */}
          <div className="h-16 flex items-center gap-2.5 px-6 border-b border-white/5 select-none">
            <div className="h-8 w-8 rounded-full bg-blue-500/10 flex items-center justify-center border border-blue-500/20 animate-pulse shadow-[0_0_12px_rgba(59,130,246,0.35)]">
              <Globe className="h-4.5 w-4.5 text-blue-400" />
            </div>
            <span className="text-sm font-bold tracking-[0.25em] uppercase text-white animate-pulse drop-shadow-[0_0_8px_rgba(59,130,246,0.3)]">TechHelp</span>
          </div>

          {/* Lista de navegación dinámica */}
          <nav className="flex-1 px-4 py-6 space-y-1.5 overflow-y-auto">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink 
                  key={item.path} 
                  to={item.path} 
                  end={item.end}
                  className={navLinkClass}
                >
                  {({ isActive }) => (
                    <>
                      <div className="flex items-center gap-3">
                        <Icon className="h-5 w-5 stroke-[1.8]" />
                        <span>{item.name}</span>
                      </div>
                      {isActive && (
                        <div className="absolute right-0 top-0 bottom-0 w-[3px] bg-blue-500" />
                      )}
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Botón de cierre de sesión en el pie de página con margen de seguridad pb-6 */}
        <div className="p-4 border-t border-white/10 pb-6">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-500/5 transition duration-200 text-sm font-medium"
          >
            <LogOut className="h-5 w-5 stroke-[1.8]" />
            <span>Cerrar Sesión</span>
          </button>
        </div>
      </aside>

      {/* Contenido del diseño principal: desplazado con ml-64 */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden ml-64">
        
        {/* Panel de navegación de la barra superior */}
        <header className="h-16 bg-[#22262B] border-b border-white/10 flex items-center justify-between px-8 z-10 shrink-0">
          
          <div className="flex items-center gap-4">
            <div className="text-sm font-semibold text-white/40 tracking-wider uppercase">
              {role ? `Espacio del ${role}` : 'Área de trabajo'}
            </div>

            {/* Banner indicador de alerta sin conexión */}
            {!isOnline && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-orange-500/10 border border-orange-500/20 text-orange-400 rounded text-[11px] font-semibold animate-pulse select-none">
                <WifiOff className="h-3.5 w-3.5 shrink-0" />
                <span>Modo Sin Conexión - Mostrando datos guardados</span>
              </div>
            )}
          </div>

          {/* Perfil de usuario y detalles de la insignia */}
          <div className="flex items-center gap-3.5">
            {/* Insignias de rol */}
            <span className={`px-2 py-0.5 text-[9px] font-bold rounded uppercase tracking-wider ${
              role === 'Administrador' 
                ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                : role === 'Tecnico'
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  : 'bg-[#00D2FF]/10 text-[#00D2FF] border border-[#00D2FF]/20'
            }`}>
              {role}
            </span>

            {/* Bloque de texto de usuario */}
            <div className="flex flex-col text-right hidden sm:flex">
              <span className="text-xs font-semibold text-white/90">{userName || 'Usuario'}</span>
              <span className="text-[10px] text-white/40">{user}</span>
            </div>
            
            {/* Icono de perfil de usuario mínimo */}
            <div className="h-8 w-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-white/80 select-none">
              <User className="h-4.5 w-4.5" />
            </div>
          </div>
        </header>

        {/* Contenedor de renderizado dinámico de salida infantil */}
        <main className="flex-1 overflow-y-auto p-8 bg-[#1A1D20]">
          <Outlet />
        </main>
      </div>

    </div>
  );
};

export default DashboardLayout;