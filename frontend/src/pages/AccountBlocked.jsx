import React from 'react';
import { useAuthStore } from '../store/authStore';
import { ShieldAlert, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const AccountBlocked = () => {
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-[#14171a] flex flex-col justify-center items-center p-4 relative overflow-hidden">
      {/* Efectos radiales brillantes de fondo. */}
      <div className="absolute top-1/4 left-1/4 w-[350px] h-[350px] rounded-full bg-red-500/5 blur-[120px] pointer-events-none select-none" />
      <div className="absolute bottom-1/4 right-1/4 w-[350px] h-[350px] rounded-full bg-red-600/5 blur-[120px] pointer-events-none select-none" />

      <div className="w-full max-w-md bg-[#22262B]/30 border border-red-500/20 backdrop-blur-md rounded-2xl p-8 text-center space-y-6 shadow-2xl relative z-10">
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center animate-pulse">
            <ShieldAlert className="h-8 w-8 text-red-500" />
          </div>
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-bold tracking-wide text-white uppercase">Acceso Suspendido</h2>
          <p className="text-xs text-white/50 leading-relaxed">
            Esta cuenta ha sido suspendida temporalmente por el Administrador.
          </p>
          <p className="text-xs text-red-400 font-semibold leading-relaxed">
            Por favor, póngase en contacto con soporte técnico.
          </p>
        </div>

        <div className="pt-2">
          <button
            onClick={handleLogout}
            className="w-full py-2.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 hover:border-red-500/50 rounded-lg text-xs font-bold tracking-wider transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer"
          >
            <LogOut className="h-4 w-4" />
            <span>SALIR</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default AccountBlocked;