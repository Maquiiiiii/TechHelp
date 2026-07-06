import React, { useEffect, useState } from 'react';
import api from '../utils/api';
import { useAuthStore } from '../store/authStore';
import { Shield, ShieldAlert, Cpu, Network, Clock, RotateCw } from 'lucide-react';

const Audit = () => {
  const { role } = useAuthStore();

  // estados centrales
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // 1. Guardia RBAC
  const isAuthorized = role === 'Administrador';

  const fetchLogs = async () => {
    try {
      const response = await api.get('/dashboard/logs');
      setLogs(response.data);
      setErrorMsg('');
    } catch (err) {
      console.error('Error fetching audit logs:', err);
      setErrorMsg('No se pudieron recuperar los registros del historial de auditoría.');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchLogs();
    setIsRefreshing(false);
  };

  useEffect(() => {
    if (!isAuthorized) {
      setLoading(false);
      return;
    }

    fetchLogs();
  }, [isAuthorized]);

  // Estilos de ayuda de insignias de estado
  const getStatusBadge = (status) => {
    switch (status) {
      case 'Abierto':
        return 'bg-white/10 text-white/70 border border-white/10';
      case 'Asignado':
        return 'bg-[#0066FF]/20 text-[#00D2FF] border border-[#0066FF]/35';
      case 'En Proceso':
        return 'bg-amber-500/10 text-amber-400 border border-amber-500/20';
      case 'En Espera':
        return 'bg-purple-500/10 text-purple-400 border border-purple-500/20';
      case 'Resuelto':
      case 'Cerrado':
        return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
      default:
        return 'bg-white/5 text-white/70 border border-transparent';
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 w-full flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
        <span className="text-sm text-white/40 tracking-wider">Cargando registros forenses...</span>
      </div>
    );
  }

  // Bloque de acceso RBAC
  if (!isAuthorized) {
    return (
      <div className="max-w-md mx-auto mt-16 text-center space-y-4 p-8 bg-red-950/10 border border-red-500/10 rounded-md">
        <div className="flex justify-center">
          <ShieldAlert className="h-14 w-14 text-red-500" />
        </div>
        <h2 className="text-lg font-bold text-white uppercase tracking-wider">Acceso Denegado</h2>
        <p className="text-xs text-white/40 leading-relaxed">
          Esta bitácora forense de auditoría inmutable está restringida exclusivamente a **Administradores**. Su rol actual es <strong className="text-red-400">{role}</strong>.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      
      {/* encabezamiento */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold tracking-wide text-white">Historial de Auditoría Forense</h2>
          <p className="text-xs text-white/40 mt-1">Bitácora inmutable de eventos de transición de estados y origen de red.</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="w-9 h-9 flex items-center justify-center bg-white/5 border border-white/10 hover:border-white/20 text-zinc-300 hover:text-white rounded-lg transition-all duration-200 disabled:opacity-50 shadow-sm shrink-0"
          title="Refrescar logs"
        >
          <RotateCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Error principal */}
      {errorMsg && (
        <div className="p-4 bg-orange-950/10 border border-orange-500/10 rounded text-center">
          <span className="text-xs font-semibold text-orange-400">{errorMsg}</span>
        </div>
      )}

      {/* Tabla de registros */}
      <div className="w-full overflow-x-auto rounded bg-[#22262B]/30 border border-white/5">
        {logs.length === 0 ? (
          <div className="p-8 text-center text-sm text-white/30">
            No se han registrado transiciones de estados en la bitácora.
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/5 bg-[#22262B]/50">
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">ID DEL TICKET (HEX)</th>
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">ESTADO ANTERIOR</th>
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">ESTADO NUEVO</th>
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">IP DE ORIGEN</th>
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">FECHA Y HORA (UTC)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {logs.map((log) => (
                <tr key={log._id} className="hover:bg-white/5 transition duration-150">
                  <td className="py-4 px-6 text-sm font-semibold text-[#00D2FF] font-mono">{log.ticket_id}</td>
                  <td className="py-4 px-6">
                    <span className={`px-2 py-0.5 text-[10px] font-semibold rounded ${getStatusBadge(log.estado_anterior)}`}>
                      {log.estado_anterior}
                    </span>
                  </td>
                  <td className="py-4 px-6">
                    <span className={`px-2 py-0.5 text-[10px] font-semibold rounded ${getStatusBadge(log.estado_nuevo)}`}>
                      {log.estado_nuevo}
                    </span>
                  </td>
                  <td className="py-4 px-6 text-xs text-white/60 font-mono">
                    <span className="flex items-center gap-1">
                      <Network className="h-3 w-3 text-white/30" />
                      {log.ip_origen}
                    </span>
                  </td>
                  <td className="py-4 px-6 text-xs text-white/50 font-mono">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3 text-white/30" />
                      {new Date(log.timestamp).toISOString()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

    </div>
  );
};

export default Audit;