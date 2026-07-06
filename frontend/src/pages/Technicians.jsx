import React, { useEffect, useState } from 'react';
import api from '../utils/api';
import { useAuthStore } from '../store/authStore';
import { useFilterStore } from '../store/filterStore';
import { 
  Users, 
  Plus, 
  X, 
  ShieldAlert, 
  UserCheck,
  Trash2,
  RotateCw
} from 'lucide-react';

const Technicians = () => {
  const { role } = useAuthStore();
  const { techEspecialidad, setTechEspecialidad } = useFilterStore();

  // estados centrales
  const [technicians, setTechnicians] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Estados modales y de forma
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [rut, setRut] = useState('');
  const [email, setEmail] = useState('');
  const [especialidad, setEspecialidad] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [tempPassword, setTempPassword] = useState('');

  // 1. Verificación RBAC
  const isAuthorized = role === 'Administrador';

  const fetchTechnicians = async () => {
    try {
      const params = {};
      if (techEspecialidad) {
        params.especialidad = techEspecialidad;
      }
      const response = await api.get('/technicians', { params });
      setTechnicians(response.data);
      setErrorMsg('');
    } catch (err) {
      console.error('Error fetching technicians:', err);
      setErrorMsg('No se pudieron recuperar los perfiles de los técnicos.');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchTechnicians();
    setIsRefreshing(false);
  };

  const handleDelete = async (id, version) => {
    const confirmed = window.confirm("¿Está seguro de que desea eliminar este técnico? Esta acción no se puede deshacer.");
    if (!confirmed) return;

    try {
      await api.delete(`/technicians/${id}?version=${version}`);
      fetchTechnicians();
    } catch (err) {
      console.error('Error deleting technician:', err);
      const msg = err.response?.data?.error || 'Error al eliminar el técnico.';
      alert(msg);
    }
  };

  const handleStatusChange = async (e, techId, currentStatus, currentVersion) => {
    e.preventDefault();
    e.stopPropagation();

    const nextStatus = currentStatus === 'Disponible' 
      ? 'En Terreno' 
      : (currentStatus === 'En Terreno' ? 'Licencia' : 'Disponible');

    try {
      await api.put(`/technicians/${techId}/status`, {
        status: nextStatus,
        version: currentVersion
      });
      fetchTechnicians();
    } catch (err) {
      console.error('Error updating status:', err);
      const msg = err.response?.data?.error || err.response?.data?.detail || 'Error al cambiar la disponibilidad.';
      alert(msg);
    }
  };

  useEffect(() => {
    if (!isAuthorized) {
      setLoading(false);
      return;
    }
    fetchTechnicians();
  }, [isAuthorized, techEspecialidad]);

  // Manejar el envío de nuevos técnicos
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError('');
    setSubmitting(true);

    try {
      const response = await api.post('/technicians', {
        name,
        rut,
        email,
        especialidad
      });
      
      // Almacenar la contraseña generada, cerrar el modal y actualizar la lista
      setTempPassword(response.data.temp_password || '');
      setIsModalOpen(false);
      setName('');
      setRut('');
      setEmail('');
      setEspecialidad('');
      fetchTechnicians();
    } catch (err) {
      console.error('Error creating technician:', err);
      const msg = err.response?.data?.detail || 'Error al registrar el técnico. Verifique el RUT u otros campos.';
      setSubmitError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // Estilos de ayuda para la insignia de estado
  const getStatusBadge = (status) => {
    switch (status) {
      case 'Disponible':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Disponible</span>;
      case 'En Terreno':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">En Terreno</span>;
      case 'Licencia':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-red-500/10 text-red-400 border border-red-500/20">Licencia</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-white/5 text-white/70">{status}</span>;
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 w-full flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
        <span className="text-sm text-white/40 tracking-wider">Cargando técnicos...</span>
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
          Esta consola de administración está reservada estrictamente para **Administradores**. Su rol actual es <strong className="text-red-400">{role}</strong>.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 relative">
      
      {/* Sección de encabezado */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold tracking-wide text-white">Técnicos</h2>
          <p className="text-xs text-white/40 mt-1">Consola de administración, especialidades y disponibilidad del personal.</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 shadow-[0_0_10px_rgba(0,102,255,0.15)]"
        >
          <Plus className="h-4 w-4" />
          <span>NUEVO TÉCNICO</span>
        </button>
      </div>

      {/* Panel de filtro especial */}
      <div className="flex items-center justify-between bg-[#22262B]/30 border border-white/5 p-4 rounded-md">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-white/40 uppercase font-bold tracking-wider mr-2">Filtrar por Especialidad:</span>
          {['', 'Hardware', 'Software', 'Redes'].map((esp) => (
            <button
              key={esp}
              onClick={() => setTechEspecialidad(esp)}
              className={`px-3 py-1.5 text-xs font-semibold rounded border transition duration-200 uppercase tracking-wider ${
                techEspecialidad === esp
                  ? 'bg-[#0066FF] border-transparent text-white shadow-[0_0_10px_rgba(0,102,255,0.15)]'
                  : 'bg-[#22262B] border-white/10 text-white/60 hover:text-white hover:border-white/20'
              }`}
            >
              {esp === '' ? 'Todos' : esp}
            </button>
          ))}
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="w-8 h-8 flex items-center justify-center bg-white/5 border border-white/10 hover:border-white/20 text-zinc-300 hover:text-white rounded-lg transition-all duration-200 disabled:opacity-50 shadow-sm shrink-0"
          title="Refrescar datos"
        >
          <RotateCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Diseño de error principal */}
      {errorMsg && (
        <div className="p-4 bg-orange-950/10 border border-orange-500/10 rounded text-center">
          <span className="text-xs font-semibold text-orange-400">{errorMsg}</span>
        </div>
      )}

      {/* Lista de mesa de técnicos */}
      <div className="w-full overflow-x-auto rounded bg-[#22262B]/30 border border-white/5">
        {technicians.length === 0 ? (
          <div className="p-8 text-center text-sm text-white/30">
            No se han encontrado técnicos con los criterios ingresados.
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/5 bg-[#22262B]/50">
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">ID SECUENCIAL</th>
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">TÉCNICO</th>
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">RUT</th>
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">CORREO ELECTRÓNICO</th>
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">ESPECIALIDAD</th>
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">DISPONIBILIDAD</th>
                <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider text-right">ACCIONES</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {technicians.map((tech) => (
                <tr key={tech._id} className="hover:bg-white/5 transition duration-150">
                  <td className="py-4 px-6 text-sm font-semibold text-[#00D2FF] font-mono">TEC-{tech.tech_id}</td>
                  <td className="py-4 px-6 text-sm font-semibold text-white/90">{tech.name}</td>
                  <td className="py-4 px-6 text-sm font-semibold text-white/60 font-mono">{tech.rut}</td>
                  <td className="py-4 px-6 text-sm text-white/60">{tech.email}</td>
                  <td className="py-4 px-6 text-sm text-white/80">{tech.especialidad}</td>
                  <td className="py-4 px-6">
                    <button
                      onClick={(e) => handleStatusChange(e, tech._id, tech.status, tech.__v || 0)}
                      className="hover:opacity-80 transition duration-150 focus:outline-none"
                      title="Haga clic para cambiar la disponibilidad"
                    >
                      {getStatusBadge(tech.status)}
                    </button>
                  </td>
                  <td className="py-4 px-6 text-sm text-right">
                    <button
                      onClick={() => handleDelete(tech._id, tech.__v || 0)}
                      className="p-1 text-white/45 hover:text-red-500 hover:bg-red-500/10 rounded transition duration-150 inline-flex items-center"
                      title="Eliminar técnico"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Superposición modal de registro */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-[#22262B] border border-white/10 rounded-md p-6 space-y-6 shadow-2xl relative">
            
            {/* Encabezado modal */}
            <div className="flex justify-between items-center pb-2 border-b border-white/5">
              <div className="flex items-center gap-2">
                <UserCheck className="h-5 w-5 text-[#00D2FF]" />
                <h3 className="text-sm font-bold uppercase tracking-wider text-white">Registrar Nuevo Técnico</h3>
              </div>
              <button 
                onClick={() => {
                  setIsModalOpen(false);
                  setSubmitError('');
                }} 
                className="text-white/40 hover:text-white transition duration-150"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Notificaciones de errores */}
            {submitError && (
              <span className="text-xs font-medium text-orange-400 bg-orange-950/15 border border-orange-500/10 px-3 py-2 rounded block leading-relaxed">
                {submitError}
              </span>
            )}

            {/* Forma modal */}
            <form onSubmit={handleSubmit} className="space-y-4">
              
              {/* Campo de nombre */}
              <div className="space-y-1.5">
                <label className="block text-[10px] font-semibold text-white/40 uppercase tracking-wider">Nombre del Técnico</label>
                <input
                  type="text"
                  required
                  disabled={submitting}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Juan Pérez"
                  className="w-full px-3 py-2 bg-transparent text-[#FFFFFF] placeholder-white/20 border-b border-white/10 focus:outline-none focus:border-[#00D2FF] transition duration-200 text-xs"
                />
              </div>

              {/* campoRUT */}
              <div className="space-y-1.5">
                <label className="block text-[10px] font-semibold text-white/40 uppercase tracking-wider">RUT (Formato Chileno)</label>
                <input
                  type="text"
                  required
                  disabled={submitting}
                  value={rut}
                  onChange={(e) => setRut(e.target.value)}
                  placeholder="12.345.678-9"
                  className="w-full px-3 py-2 bg-transparent text-[#FFFFFF] placeholder-white/20 border-b border-white/10 focus:outline-none focus:border-[#00D2FF] transition duration-200 text-xs font-mono"
                />
              </div>

              {/* Campo de correo electrónico */}
              <div className="space-y-1.5">
                <label className="block text-[10px] font-semibold text-white/40 uppercase tracking-wider">Correo Electrónico</label>
                <input
                  type="email"
                  required
                  disabled={submitting}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="juan.perez@techhelp.cl"
                  className="w-full px-3 py-2 bg-transparent text-[#FFFFFF] placeholder-white/20 border-b border-white/10 focus:outline-none focus:border-[#00D2FF] transition duration-200 text-xs"
                />
              </div>

              {/* Campo de especialidad */}
              <div className="space-y-1.5">
                <label className="block text-[10px] font-semibold text-white/40 uppercase tracking-wider">Especialidad</label>
                <select
                  required
                  disabled={submitting}
                  value={especialidad}
                  onChange={(e) => setEspecialidad(e.target.value)}
                  className="w-full px-3 py-2 bg-[#22262B] text-[#FFFFFF] border-b border-white/10 focus:outline-none focus:border-[#00D2FF] transition duration-200 text-xs cursor-pointer"
                >
                  <option value="" disabled>Seleccione especialidad</option>
                  <option value="Hardware">Hardware</option>
                  <option value="Software">Software</option>
                  <option value="Redes">Redes</option>
                </select>
              </div>

              {/* Comportamiento */}
              <div className="flex justify-end gap-3 pt-4 border-t border-white/5">
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => {
                    setIsModalOpen(false);
                    setSubmitError('');
                  }}
                  className="px-4 py-2 text-white/60 hover:text-white text-xs font-bold uppercase tracking-wider"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting || !name || !rut || !email || !especialidad}
                  className="px-4 py-2 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 shadow-[0_0_10px_rgba(0,102,255,0.15)] disabled:opacity-40"
                >
                  {submitting ? 'REGISTRANDO...' : 'REGISTRAR'}
                </button>
              </div>

            </form>
          </div>
        </div>
      )}
      {/* Modalidad exitosa de contraseña temporal */}
      {tempPassword && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-[#22262B] border border-white/10 rounded-md p-6 space-y-6 shadow-2xl relative text-center">
            <div className="flex justify-center">
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-full animate-pulse">
                <UserCheck className="h-7 w-7" />
              </div>
            </div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Técnico Creado con Éxito</h3>
            
            <div className="p-4 bg-white/5 border border-white/5 rounded space-y-2">
              <p className="text-[10px] text-white/45 font-semibold uppercase tracking-wider">Contraseña Temporal</p>
              <div className="text-base font-mono font-extrabold text-[#00D2FF] tracking-wider select-all">
                {tempPassword}
              </div>
              <p className="text-[10px] text-amber-400 font-semibold leading-relaxed">
                ¡Cópiela ahora! Por motivos de seguridad, no se volverá a mostrar.
              </p>
            </div>

            <button
              onClick={() => setTempPassword('')}
              className="w-full py-2 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 uppercase"
            >
              Entendido
            </button>
          </div>
        </div>
      )}

    </div>
  );
};

export default Technicians;