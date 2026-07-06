import React, { useEffect, useState } from 'react';
import api from '../utils/api';
import { useAuthStore } from '../store/authStore';
import { useFilterStore } from '../store/filterStore';
import { 
  Building, 
  Plus, 
  X, 
  ShieldAlert, 
  Lock,
  Unlock,
  RotateCw
} from 'lucide-react';

const Organizations = () => {
  const { role } = useAuthStore();
  const { orgSearch, setOrgSearch } = useFilterStore();

  // estados centrales
  const [organizations, setOrganizations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Estado de búsqueda local para antirrebote
  const [localOrgSearch, setLocalOrgSearch] = useState(orgSearch);

  // Estados modales y de forma
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [rut, setRut] = useState('');
  const [email, setEmail] = useState('');
  const [industria, setIndustria] = useState('');
  const [tierContractual, setTierContractual] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // 1. Verificación RBAC
  const isAuthorized = role === 'Administrador';

  // Estado de búsqueda antirrebote
  useEffect(() => {
    const handler = setTimeout(() => {
      setOrgSearch(localOrgSearch);
    }, 300);
    return () => clearTimeout(handler);
  }, [localOrgSearch, setOrgSearch]);

  const fetchOrganizations = async () => {
    try {
      const response = await api.get('/organizations', {
        params: orgSearch ? { search: orgSearch } : {}
      });
      setOrganizations(response.data);
      setErrorMsg('');
    } catch (err) {
      console.error('Error fetching organizations:', err);
      setErrorMsg('No se pudieron recuperar las organizaciones.');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchOrganizations();
    setIsRefreshing(false);
  };

  const handleToggleActive = async (id, version, currentActive) => {
    const actionText = currentActive ? 'bloquear/desactivar' : 'desbloquear/activar';
    const confirmed = window.confirm(`¿Está seguro de que desea ${actionText} esta organización?`);
    if (!confirmed) return;

    try {
      await api.put(`/organizations/${id}/toggle-status?version=${version}`);
      fetchOrganizations();
    } catch (err) {
      console.error('Error toggling organization status:', err);
      const msg = err.response?.data?.error || 'Error al cambiar el estado de la organización.';
      alert(msg);
    }
  };

  useEffect(() => {
    if (!isAuthorized) {
      setLoading(false);
      return;
    }
    fetchOrganizations();
  }, [isAuthorized, orgSearch]);

  // Manejar el envío de nuevas organizaciones
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError('');
    setSubmitting(true);

    try {
      await api.post('/organizations', {
        name,
        rut,
        email,
        industria,
        tier_contractual: tierContractual
      });
      
      // Restablecer campos de formulario
      setIsModalOpen(false);
      setName('');
      setRut('');
      setEmail('');
      setIndustria('');
      setTierContractual('');
      fetchOrganizations();
    } catch (err) {
      console.error('Error creating organization:', err);
      const msg = err.response?.data?.detail || 'Error al registrar la organización. Verifique el RUT u otros campos.';
      setSubmitError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center w-full h-64 gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
        <span className="text-sm tracking-wider text-white/40">Cargando organizaciones...</span>
      </div>
    );
  }

  // Bloque de acceso RBAC
  if (!isAuthorized) {
    return (
      <div className="max-w-md p-8 mx-auto mt-16 space-y-4 text-center border rounded-md bg-red-950/10 border-red-500/10">
        <div className="flex justify-center">
          <ShieldAlert className="text-red-500 h-14 w-14" />
        </div>
        <h2 className="text-lg font-bold tracking-wider text-white uppercase">Acceso Denegado</h2>
        <p className="text-xs leading-relaxed text-white/40">
          Esta consola de administración está reservada estrictamente para **Administradores**. Su rol actual es <strong className="text-red-400">{role}</strong>.
        </p>
      </div>
    );
  }

  return (
    <div className="relative space-y-6">
      
      {/* Sección de encabezado */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-wide text-white">Organizaciones</h2>
          <p className="mt-1 text-xs text-white/40">Consola de administración y registro de clientes TechHelp.</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 shadow-[0_0_10px_rgba(0,102,255,0.15)]"
        >
          <Plus className="w-4 h-4" />
          <span>NUEVA ORGANIZACIÓN</span>
        </button>
      </div>

      {/* Barra de búsqueda inteligente y actualización manual */}
      <div className="flex items-center gap-3">
        <div className="w-full max-w-md">
          <input
            type="text"
            placeholder="Buscar por Nombre, RUT, Email o Industria..."
            value={localOrgSearch}
            onChange={(e) => setLocalOrgSearch(e.target.value)}
            className="w-full h-10 bg-[#22262B]/30 text-white text-xs border border-white/10 rounded px-4 focus:outline-none focus:border-[#00D2FF] transition duration-200 placeholder-white/30"
          />
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="w-10 h-10 flex items-center justify-center bg-white/5 border border-white/10 hover:border-white/20 text-zinc-300 hover:text-white rounded-lg transition-all duration-200 disabled:opacity-50 shadow-sm shrink-0"
          title="Refrescar datos"
        >
          <RotateCw className={`h-4.5 w-4.5 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Diseño de error principal */}
      {errorMsg && (
        <div className="p-4 text-center border rounded bg-orange-950/10 border-orange-500/10">
          <span className="text-xs font-semibold text-orange-400">{errorMsg}</span>
        </div>
      )}

      {/* Lista de tablas de organizaciones */}
      <div className="w-full overflow-x-auto rounded bg-[#22262B]/30 border border-white/5">
        {organizations.length === 0 ? (
          <div className="p-8 text-sm text-center text-white/30">
            No se han encontrado organizaciones que coincidan con la búsqueda.
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/5 bg-[#22262B]/50">
                <th className="px-6 py-4 text-xs font-semibold tracking-wider text-white/50">ORGANIZACIÓN</th>
                <th className="px-6 py-4 text-xs font-semibold tracking-wider text-white/50">RUT</th>
                <th className="px-6 py-4 text-xs font-semibold tracking-wider text-white/50">EMAIL DE CONTACTO</th>
                <th className="px-6 py-4 text-xs font-semibold tracking-wider text-white/50">INDUSTRIA</th>
                <th className="px-6 py-4 text-xs font-semibold tracking-wider text-center text-white/50">TICKETS TOTALES</th>
                <th className="px-6 py-4 text-xs font-semibold tracking-wider text-right text-white/50">ACCIONES</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {organizations.map((org) => (
                <tr key={org._id} className="transition duration-150 hover:bg-white/5">
                  <td className="px-6 py-4 text-sm font-semibold text-white/90">{org.name}</td>
                  <td className="py-4 px-6 text-sm font-semibold text-[#00D2FF] font-mono">{org.rut}</td>
                  <td className="px-6 py-4 text-sm text-white/60">{org.email}</td>
                  <td className="px-6 py-4 text-sm text-white/40">{org.industria || 'No Especificada'}</td>
                  <td className="px-6 py-4 text-sm text-center">
                    <span className="px-2.5 py-1 text-xs font-bold rounded bg-[#00D2FF]/10 text-[#00D2FF]">
                      {org.tickets_count || 0}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-right">
                    <button
                      onClick={() => handleToggleActive(org._id, org.__v || 0, org.activo)}
                      className={`inline-flex items-center justify-center p-1.5 transition duration-150 rounded border ${
                        org.activo 
                          ? 'text-green-400 bg-green-500/10 border-green-500/20 hover:bg-green-500/20 hover:text-green-300' 
                          : 'text-red-400 bg-red-500/10 border-red-500/20 hover:bg-red-500/20 hover:text-red-300'
                      }`}
                      title={org.activo ? "Bloquear organización" : "Desbloquear organización"}
                    >
                      {org.activo ? (
                        <Unlock className="w-4 h-4" />
                      ) : (
                        <Lock className="w-4 h-4" />
                      )}
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-lg bg-[#22262B] border border-white/10 rounded-md p-6 space-y-6 shadow-2xl relative">
            
            {/* Encabezado modal */}
            <div className="flex items-center justify-between pb-2 border-b border-white/5">
              <div className="flex items-center gap-2">
                <Building className="h-5 w-5 text-[#00D2FF]" />
                <h3 className="text-sm font-bold tracking-wider text-white uppercase">Registrar Organización</h3>
              </div>
              <button 
                onClick={() => {
                  setIsModalOpen(false);
                  setSubmitError('');
                }} 
                className="transition duration-150 text-white/40 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Notificaciones de errores */}
            {submitError && (
              <span className="block px-3 py-2 text-xs font-medium leading-relaxed text-orange-400 border rounded bg-orange-950/15 border-orange-500/10">
                {submitError}
              </span>
            )}

            {/* Forma modal */}
            <form onSubmit={handleSubmit} className="space-y-4">
              
              {/* Campo de nombre */}
              <div className="space-y-1.5">
                <label className="block text-[10px] font-semibold text-white/40 uppercase tracking-wider">Nombre de la Organización</label>
                <input
                  type="text"
                  required
                  disabled={submitting}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="TechHelp Solutions Ltd"
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
                <label className="block text-[10px] font-semibold text-white/40 uppercase tracking-wider">Correo Electrónico de Contacto</label>
                <input
                  type="email"
                  required
                  disabled={submitting}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="contacto@empresa.cl"
                  className="w-full px-3 py-2 bg-transparent text-[#FFFFFF] placeholder-white/20 border-b border-white/10 focus:outline-none focus:border-[#00D2FF] transition duration-200 text-xs"
                />
              </div>

              {/* campo de la industria */}
              <div className="space-y-1.5">
                <label className="block text-[10px] font-semibold text-white/40 uppercase tracking-wider">Industria *</label>
                <input
                  type="text"
                  required
                  disabled={submitting}
                  value={industria}
                  onChange={(e) => setIndustria(e.target.value)}
                  placeholder="Tecnología, Retail, Telecomunicaciones..."
                  className="w-full px-3 py-2 bg-transparent text-[#FFFFFF] placeholder-white/20 border-b border-white/10 focus:outline-none focus:border-[#00D2FF] transition duration-200 text-xs"
                />
              </div>

              {/* Campo contractual de nivel */}
              <div className="space-y-1.5">
                <label className="block text-[10px] font-semibold text-white/40 uppercase tracking-wider">Nivel de Soporte Contractual</label>
                <select
                  required
                  disabled={submitting}
                  value={tierContractual}
                  onChange={(e) => setTierContractual(e.target.value)}
                  className="w-full px-3 py-2 bg-[#22262B] text-[#FFFFFF] border-b border-white/10 focus:outline-none focus:border-[#00D2FF] transition duration-200 text-xs appearance-none pr-8"
                  style={{
                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke-width='1.5' stroke='%239CA3AF' class='w-4 h-4'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='m19.5 8.25-7.5 7.5-7.5-7.5'/%3E%3C/svg%3E")`,
                    backgroundRepeat: 'no-repeat',
                    backgroundPosition: 'right 0.75rem center',
                    backgroundSize: '1rem'
                  }}
                >
                  <option value="" disabled className="bg-[#22262B] text-white/50">Seleccione un nivel de soporte...</option>
                  <option value="Bronce" className="bg-[#22262B] text-white">Bronce</option>
                  <option value="Plata" className="bg-[#22262B] text-white">Plata</option>
                  <option value="Oro" className="bg-[#22262B] text-white">Oro</option>
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
                  className="px-4 py-2 text-xs font-bold tracking-wider uppercase text-white/60 hover:text-white"
                >
                  Cancelar
                </button>
                <button
                  type="submit" 
                  disabled={submitting || !name || !rut || !email || !tierContractual || !industria}
                  className="px-4 py-2 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 shadow-[0_0_10px_rgba(0,102,255,0.15)] disabled:opacity-40"
                >
                  {submitting ? 'REGISTRANDO...' : 'REGISTRAR'}
                </button>
              </div>

            </form>
          </div>
        </div>
      )}

    </div>
  );
};

export default Organizations;