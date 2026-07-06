import React, { useEffect, useState } from 'react';
import api from '../utils/api';
import { useAuthStore } from '../store/authStore';
import { Clock, ShieldAlert, CheckCircle2, AlertTriangle, UserCheck } from 'lucide-react';

const Availability = () => {
  const { role } = useAuthStore();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [updating, setUpdating] = useState(false);

  const fetchProfile = async () => {
    try {
      setLoading(true);
      const response = await api.get('/technicians/me');
      setProfile(response.data);
      setErrorMsg('');
    } catch (err) {
      console.error('Error fetching technician profile:', err);
      setErrorMsg('No se pudo recuperar su perfil de técnico. Intente recargando la página.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (role === 'Tecnico') {
      fetchProfile();
    } else {
      setLoading(false);
    }
  }, [role]);

  const handleStatusUpdate = async (newStatus) => {
    if (!profile) return;
    setUpdating(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      const response = await api.put('/technicians/me/status', {
        status: newStatus,
        version: profile.__v || 0
      });
      setProfile(response.data);
      setSuccessMsg(`Disponibilidad actualizada exitosamente a "${newStatus}".`);
      setTimeout(() => setSuccessMsg(''), 3000);
    } catch (err) {
      console.error('Error updating status:', err);
      const msg = err.response?.data?.detail || 'Error al actualizar el estado. Intente nuevamente.';
      setErrorMsg(msg);
    } finally {
      setUpdating(false);
    }
  };

  if (role !== 'Tecnico') {
    return (
      <div className="max-w-md mx-auto mt-16 text-center space-y-4 p-8 bg-red-950/10 border border-red-500/10 rounded-md">
        <div className="flex justify-center">
          <ShieldAlert className="h-14 w-14 text-red-500" />
        </div>
        <h2 className="text-lg font-bold text-white uppercase tracking-wider">Acceso Denegado</h2>
        <p className="text-xs text-white/40 leading-relaxed">
          Esta sección está reservada exclusivamente para **Técnicos**. Su rol es <strong className="text-red-400">{role}</strong>.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-64 w-full flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
        <span className="text-sm text-white/40 tracking-wider">Cargando disponibilidad...</span>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      
      {/* Título de la página */}
      <div>
        <h2 className="text-xl font-bold tracking-wide text-white">Mi Disponibilidad</h2>
        <p className="text-xs text-white/40 mt-1">Gestione su estado operativo actual en el sistema de despacho automatizado.</p>
      </div>

      {/* Mensajes */}
      {errorMsg && (
        <div className="p-3 bg-red-950/10 border border-red-500/10 rounded text-center">
          <span className="text-xs font-semibold text-red-400">{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-3 bg-emerald-950/10 border border-emerald-500/10 rounded text-center">
          <span className="text-xs font-semibold text-emerald-400">{successMsg}</span>
        </div>
      )}

      {profile && (
        <div className="bg-[#22262B] border border-white/10 rounded-md p-6 space-y-6 shadow-xl">
          
          {/* resumen */}
          <div className="flex items-center justify-between border-b border-white/5 pb-4">
            <div className="space-y-0.5">
              <h3 className="text-sm font-bold text-white">{profile.name}</h3>
              <p className="text-[10px] text-white/40 font-mono">TEC-{profile.tech_id} • {profile.especialidad}</p>
            </div>
            <div>
              <span className={`px-2.5 py-1 text-xs font-bold rounded ${
                profile.status === 'Disponible' 
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                  : profile.status === 'En Terreno'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {profile.status}
              </span>
            </div>
          </div>

          {/* Cuadro de acción */}
          <div className="space-y-3">
            <h4 className="text-[10px] font-bold text-white/55 uppercase tracking-wider">Cambiar mi Estado Operativo</h4>
            
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              
              {/* Opción 1: Disponible */}
              <button
                onClick={() => handleStatusUpdate('Disponible')}
                disabled={updating || profile.status === 'Disponible'}
                className={`p-4 border rounded text-left transition duration-200 ${
                  profile.status === 'Disponible'
                    ? 'bg-emerald-500/10 border-emerald-500 text-emerald-400 cursor-default'
                    : 'bg-white/5 border-white/5 hover:border-emerald-500/30 text-white/70 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <UserCheck className="h-4 w-4" />
                  <span className="text-xs font-bold uppercase tracking-wider">Disponible</span>
                </div>
                <p className="text-[9px] opacity-60 leading-normal">
                  Listo para recibir asignaciones automáticas de tickets según especialidad.
                </p>
              </button>

              {/* Opción 2: En Terreno */}
              <button
                onClick={() => handleStatusUpdate('En Terreno')}
                disabled={updating || profile.status === 'En Terreno'}
                className={`p-4 border rounded text-left transition duration-200 ${
                  profile.status === 'En Terreno'
                    ? 'bg-amber-500/10 border-amber-500 text-amber-400 cursor-default'
                    : 'bg-white/5 border-white/5 hover:border-amber-500/30 text-white/70 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Clock className="h-4 w-4" />
                  <span className="text-xs font-bold uppercase tracking-wider">En Terreno</span>
                </div>
                <p className="text-[9px] opacity-60 leading-normal">
                  Realizando visitas operativas. Recibe asignaciones de baja prioridad.
                </p>
              </button>

              {/* Opción 3: Licencia */}
              <button
                onClick={() => handleStatusUpdate('Licencia')}
                disabled={updating || profile.status === 'Licencia'}
                className={`p-4 border rounded text-left transition duration-200 ${
                  profile.status === 'Licencia'
                    ? 'bg-red-500/10 border-red-500 text-red-400 cursor-default'
                    : 'bg-white/5 border-white/5 hover:border-red-500/30 text-white/70 hover:text-white'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="text-xs font-bold uppercase tracking-wider">Licencia</span>
                </div>
                <p className="text-[9px] opacity-60 leading-normal">
                  Ausente por motivos de salud u otros permisos. No se asignarán tickets.
                </p>
              </button>

            </div>
          </div>

        </div>
      )}

    </div>
  );
};

export default Availability;