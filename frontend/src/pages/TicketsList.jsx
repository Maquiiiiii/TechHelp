import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RotateCw } from 'lucide-react';
import api from '../utils/api';
import { useAuthStore } from '../store/authStore';
import { useFilterStore } from '../store/filterStore';

const TicketsList = () => {
  const navigate = useNavigate();
  const { role, especialidad, setEspecialidad } = useAuthStore();
  
  // Estados y acciones del almacén de filtros de desestructuración
  const {
    ticketSearch, setTicketSearch,
    ticketPriority, setTicketPriority,
    ticketStatus, setTicketStatus,
    ticketCategory, setTicketCategory,
    resetTicketFilters
  } = useFilterStore();

  const [tickets, setTickets] = useState([]);
  const [techProfile, setTechProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  // Estado local para entrada de búsqueda para implementar el rebote
  const [localSearch, setLocalSearch] = useState(ticketSearch);

  const isAssignedRoute = window.location.pathname.includes('/assigned');
  const isAllRoute = window.location.pathname.includes('/all');
  const isHistoryRoute = window.location.pathname.includes('/history');

  // Rechazar cambios de entrada de búsqueda
  useEffect(() => {
    const handler = setTimeout(() => {
      setTicketSearch(localSearch);
    }, 300);
    return () => clearTimeout(handler);
  }, [localSearch, setTicketSearch]);

  const fetchData = async (showLoadingSpinner = true) => {
    try {
      if (showLoadingSpinner) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }
      setError('');

      let currentTechProfile = techProfile;
      if (role === 'Tecnico' && !currentTechProfile) {
        try {
          const profileRes = await api.get('/technicians/me');
          currentTechProfile = profileRes.data;
          setTechProfile(profileRes.data);
          if (profileRes.data && profileRes.data.especialidad) {
            setEspecialidad(profileRes.data.especialidad);
          }
        } catch (profileErr) {
          console.error('Error fetching technician profile:', profileErr);
        }
      }

      // Crear parámetros de consulta API
      const params = {};
      
      // Verificación de múltiples inquilinos/lógica asignada por tecnología
      if (role === 'Tecnico' && isAssignedRoute && currentTechProfile) {
        params.asignado_a = currentTechProfile._id;
      }
      
      if (ticketSearch) params.search = ticketSearch;
      if (ticketPriority) params.prioridad = ticketPriority;
      if (ticketStatus) params.status = ticketStatus;
      if (ticketCategory) params.categoria = ticketCategory;

      const response = await api.get('/tickets', { params });
      setTickets(response.data);

    } catch (err) {
      console.error('Error fetching data:', err);
      setError('No se pudieron cargar los tickets de soporte. Verifique la conexión.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Vuelva a ejecutar la búsqueda/obtención cuando cambien los filtros o las rutas
  useEffect(() => {
    fetchData(true);
  }, [role, isAssignedRoute, isAllRoute, isHistoryRoute, ticketSearch, ticketPriority, ticketStatus, ticketCategory]);

  const handleRefresh = () => {
    fetchData(false);
  };

  // Devuelve el estilo de las insignias de estado.
  const getStatusBadge = (status) => {
    switch (status) {
      case 'Abierto':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-white/10 text-white/80">Abierto</span>;
      case 'Asignado':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-[#0066FF]/20 text-[#00D2FF]">Asignado</span>;
      case 'En Proceso':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-amber-500/10 text-amber-400">En Proceso</span>;
      case 'En Espera':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-purple-500/10 text-purple-400">En Espera</span>;
      case 'Resuelto':
      case 'Cerrado':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-emerald-500/10 text-emerald-400">{status}</span>;
      case 'Rechazado':
      case 'Cancelado':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-rose-500/10 text-rose-400">{status}</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded bg-white/10 text-white">{status}</span>;
    }
  };

  // Devuelve el estilo de los indicadores de prioridad.
  const getPriorityIndicator = (priority) => {
    switch (priority) {
      case 'Crítica':
        return (
          <span className="flex items-center gap-1.5 text-xs text-red-500 font-semibold">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse"></span> Crítica
          </span>
        );
      case 'Alta':
        return (
          <span className="flex items-center gap-1.5 text-xs text-orange-500 font-semibold">
            <span className="h-1.5 w-1.5 rounded-full bg-orange-500"></span> Alta
          </span>
        );
      case 'Media':
        return (
          <span className="flex items-center gap-1.5 text-xs text-yellow-500 font-semibold">
            <span className="h-1.5 w-1.5 rounded-full bg-yellow-500"></span> Media
          </span>
        );
      case 'Baja':
        return (
          <span className="flex items-center gap-1.5 text-xs text-green-500 font-semibold">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500"></span> Baja
          </span>
        );
      default:
        return <span className="text-xs text-white/60">{priority}</span>;
    }
  };

  // Filtros de interfaz adicionales basados ​​en roles de enrutamiento
  const filteredTickets = tickets.filter((t) => {
    if (role === 'Tecnico') {
      const activeEsp = especialidad || techProfile?.especialidad;
      
      if (isAssignedRoute) {
        // Devolver sólo los tickets asignados a este técnico que estén 'Asignados' o 'En Proceso'
        return t.assigned_tech_id === techProfile?._id && 
               (t.status === 'Asignado' || t.status === 'En Proceso');
      } else if (isAllRoute) {
        // "Todos los tickets" para técnicos: muestra sólo los tickets correspondientes a su especialidad
        return t.categoria === activeEsp;
      } else if (isHistoryRoute) {
        // "Historial de tickets" para técnicos: muestra sólo los tickets cerrados, resueltos o rechazados que tienen asignados
        return t.assigned_tech_id === techProfile?._id &&
               ['Resuelto', 'Cerrado', 'Rechazado'].includes(t.status);
      }
    }
    return true;
  });

  if (loading) {
    return (
      <div className="flex h-64 w-full flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
        <span className="text-sm text-white/40 tracking-wider">Cargando tickets...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Sección de encabezado */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold tracking-wide text-white">
            {role === 'Tecnico' && isAssignedRoute 
              ? 'Tickets asignados' 
              : role === 'Tecnico' && isAllRoute 
                ? 'Todos los tickets' 
                : role === 'Tecnico' && isHistoryRoute 
                  ? 'Historial de tickets' 
                  : 'Tickets de Soporte'}
          </h2>
          <p className="text-xs text-white/40 mt-1">
            {role === 'Tecnico' && isAssignedRoute 
              ? 'Listado de incidentes activos asignados a su carga de trabajo (Asignado / En Proceso).' 
              : role === 'Tecnico' && isAllRoute 
                ? 'Incidentes registrados que corresponden a su área técnica de especialidad.'
                : role === 'Tecnico' && isHistoryRoute 
                  ? 'Listado histórico de incidentes resueltos, cerrados o rechazados.'
                  : 'Listado de incidentes registrados en el sistema TechHelp.'}
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Botón Actualizar */}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className={`flex items-center gap-1.5 px-3 py-2 bg-[#22262B] hover:bg-[#2B3037] text-white text-xs font-bold rounded border border-white/10 hover:border-white/20 transition duration-200 uppercase tracking-wider ${
              refreshing ? 'opacity-50 cursor-not-allowed' : ''
            }`}
            title="Refrescar lista de tickets"
          >
            <RotateCw className={`h-3.5 w-3.5 text-[#00D2FF] ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refrescar</span>
          </button>

          {role !== 'Tecnico' && (
            <button
              onClick={() => navigate('/tickets/new')}
              className="px-4 py-2 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 shadow-[0_0_10px_rgba(0,102,255,0.15)]"
            >
              CREAR TICKET
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 text-center border rounded bg-orange-950/10 border-orange-500/10 text-orange-400 text-xs font-semibold">
          {error}
        </div>
      )}

      {/* Diseño de contenido principal con cuadrícula dinámica. */}
      <div className="flex flex-col lg:flex-row gap-6">
        
        {/* Panel izquierdo de filtros avanzados para rol CLIENTE */}
        {role === 'Cliente' && (
          <div className="w-full lg:w-64 shrink-0 bg-[#22262B]/30 border border-white/5 rounded-md p-4 space-y-5">
            <div className="flex items-center justify-between pb-2 border-b border-white/5">
              <h3 className="text-xs font-bold tracking-wider text-white uppercase">Filtros Avanzados</h3>
              {(ticketSearch || ticketPriority || ticketStatus || ticketCategory) && (
                <button
                  onClick={() => {
                    setLocalSearch('');
                    resetTicketFilters();
                  }}
                  className="text-[10px] text-[#00D2FF] hover:underline uppercase font-bold tracking-wider"
                >
                  Limpiar
                </button>
              )}
            </div>
            
            {/* Consulta de búsqueda inteligente */}
            <div className="space-y-1.5">
              <label className="text-[10px] text-white/40 uppercase font-bold tracking-wider block">Buscar por Texto</label>
              <input
                type="text"
                placeholder="Título o código (TK-XXXXX)..."
                value={localSearch}
                onChange={(e) => setLocalSearch(e.target.value)}
                className="w-full bg-[#1A1D20] text-white text-xs border border-white/10 rounded px-3 py-2.5 focus:outline-none focus:border-[#00D2FF] transition duration-200 placeholder-white/20"
              />
            </div>
            
            {/* Selección facetada de estado */}
            <div className="space-y-2">
              <label className="text-[10px] text-white/40 uppercase font-bold tracking-wider block">Estado</label>
              <div className="flex flex-col gap-1">
                {[
                  { value: '', label: 'Todos' },
                  { value: 'Abierto', label: 'Abierto' },
                  { value: 'En Proceso', label: 'En Proceso' },
                  { value: 'En Espera', label: 'En Espera' },
                  { value: 'Resuelto', label: 'Resuelto' },
                  { value: 'Cerrado', label: 'Cerrado' },
                  { value: 'Rechazado', label: 'Rechazado' }
                ].map((st) => (
                  <button
                    key={st.value}
                    type="button"
                    onClick={() => setTicketStatus(st.value)}
                    className={`w-full text-left px-2.5 py-1.5 text-xs font-semibold rounded border transition duration-200 uppercase tracking-wider ${
                      ticketStatus === st.value
                        ? 'bg-[#00D2FF]/20 border-[#00D2FF]/40 text-[#00D2FF] pl-2 border-l-2'
                        : 'bg-transparent border-transparent text-white/60 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    {st.label}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Selección facetada de categoría */}
            <div className="space-y-2">
              <label className="text-[10px] text-white/40 uppercase font-bold tracking-wider block">Categoría</label>
              <div className="flex flex-col gap-1">
                {[
                  { value: '', label: 'Todas' },
                  { value: 'Hardware', label: 'Hardware' },
                  { value: 'Software', label: 'Software' },
                  { value: 'Redes', label: 'Redes' }
                ].map((cat) => (
                  <button
                    key={cat.value}
                    type="button"
                    onClick={() => setTicketCategory(cat.value)}
                    className={`w-full text-left px-2.5 py-1.5 text-xs font-semibold rounded border transition duration-200 uppercase tracking-wider ${
                      ticketCategory === cat.value
                        ? 'bg-[#0066FF]/20 border-[#0066FF]/40 text-[#0066FF] pl-2 border-l-2'
                        : 'bg-transparent border-transparent text-white/60 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Selección facetada prioritaria */}
            <div className="space-y-2">
              <label className="text-[10px] text-white/40 uppercase font-bold tracking-wider block">Prioridad</label>
              <div className="flex flex-col gap-1">
                {[
                  { value: '', label: 'Todas' },
                  { value: 'Baja', label: 'Baja' },
                  { value: 'Media', label: 'Media' },
                  { value: 'Alta', label: 'Alta' },
                  { value: 'Crítica', label: 'Crítica' }
                ].map((prio) => (
                  <button
                    key={prio.value}
                    type="button"
                    onClick={() => setTicketPriority(prio.value)}
                    className={`w-full text-left px-2.5 py-1.5 text-xs font-semibold rounded border transition duration-200 uppercase tracking-wider ${
                      ticketPriority === prio.value
                        ? 'bg-[#E53E3E]/25 border-[#E53E3E]/45 text-[#FC8181] pl-2 border-l-2'
                        : 'bg-transparent border-transparent text-white/60 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    {prio.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Filtros de encabezado de técnico y contenido de tabla */}
        <div className="flex-1 space-y-4">
          
          {/* Barra de filtro en línea superior para funciones de TÉCNICO / ADMINISTRADOR */}
          {role !== 'Cliente' && (
            <div className="space-y-4 bg-[#22262B]/30 border border-white/5 p-4 rounded-md w-full">
              <div className="flex flex-col md:flex-row gap-4 items-center">
                {/* Entrada de búsqueda */}
                <div className="w-full md:w-1/3">
                  <input
                    type="text"
                    placeholder="Buscar por título, código o descripción..."
                    value={localSearch}
                    onChange={(e) => setLocalSearch(e.target.value)}
                    className="w-full bg-[#1A1D20] text-white text-xs border border-white/10 rounded px-3 py-2.5 focus:outline-none focus:border-[#00D2FF] transition duration-200 placeholder-white/20"
                  />
                </div>
                
                {/* Pastillas filtrantes prioritarias */}
                <div className="flex flex-wrap gap-2 w-full md:w-2/3 justify-start md:justify-end items-center">
                  <span className="text-[10px] text-white/40 uppercase font-bold tracking-wider mr-2">Prioridad:</span>
                  {['', 'Baja', 'Media', 'Alta', 'Crítica'].map((prio) => (
                    <button
                      key={prio}
                      type="button"
                      onClick={() => setTicketPriority(prio)}
                      className={`px-3 py-1.5 text-xs font-semibold rounded border transition duration-200 uppercase tracking-wider ${
                        ticketPriority === prio
                          ? 'bg-[#0066FF] border-transparent text-white shadow-[0_0_10px_rgba(0,102,255,0.15)]'
                          : 'bg-[#22262B] border-white/10 text-white/60 hover:text-white hover:border-white/20'
                      }`}
                    >
                      {prio === '' ? 'Todos' : prio}
                    </button>
                  ))}
                </div>
              </div>

              {/* Pastillas de filtro de estado */}
              <div className="flex flex-wrap gap-2 items-center pt-2 border-t border-white/5">
                <span className="text-[10px] text-white/40 uppercase font-bold tracking-wider mr-2">Estado:</span>
                {['', 'Abierto', 'Asignado', 'En Proceso', 'En Espera', 'Resuelto', 'Cerrado', 'Rechazado', 'Cancelado'].map((st) => (
                  <button
                    key={st}
                    type="button"
                    onClick={() => setTicketStatus(st)}
                    className={`px-3 py-1.5 text-xs font-semibold rounded border transition duration-200 uppercase tracking-wider ${
                      ticketStatus === st
                        ? 'bg-[#00D2FF]/20 border-[#00D2FF]/40 text-[#00D2FF] shadow-[0_0_10px_rgba(0,210,255,0.1)]'
                        : 'bg-[#22262B] border-white/10 text-white/60 hover:text-white hover:border-white/20'
                    }`}
                  >
                    {st === '' ? 'Todos' : st}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Lista de tablas */}
          <div className="w-full overflow-x-auto rounded bg-[#22262B]/30 border border-white/5">
            {filteredTickets.length === 0 ? (
              <div className="p-8 text-center text-sm text-white/30">
                No se han encontrado tickets con los criterios ingresados.
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/5 bg-[#22262B]/50">
                    <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">CÓDIGO</th>
                    <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">TÍTULO</th>
                    <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">CATEGORÍA</th>
                    <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">ESTADO</th>
                    <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-wider">PRIORIDAD</th>
                    <th className="py-4 px-6 text-xs font-semibold text-white/50 tracking-right tracking-wider text-right">ACCIONES</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredTickets.map((ticket) => (
                    <tr 
                      key={ticket._id} 
                      className="hover:bg-white/5 transition duration-150 cursor-pointer"
                      onClick={() => navigate(`/tickets/${ticket._id}`)}
                    >
                      <td className="py-4 px-6 text-sm font-semibold text-[#00D2FF] font-mono">{ticket.code}</td>
                      <td className="py-4 px-6 text-sm font-medium text-white/90 max-w-xs truncate">{ticket.title}</td>
                      <td className="py-4 px-6 text-sm text-white/60">{ticket.categoria}</td>
                      <td className="py-4 px-6">{getStatusBadge(ticket.status)}</td>
                      <td className="py-4 px-6">{getPriorityIndicator(ticket.prioridad)}</td>
                      <td className="py-4 px-6 text-right">
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/tickets/${ticket._id}`);
                          }}
                          className="px-3 py-1.5 bg-white/5 hover:bg-[#0066FF] hover:text-white text-xs font-semibold rounded text-white/80 border border-white/10 hover:border-transparent transition duration-200"
                        >
                          Ver Detalle
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          
        </div>
      </div>
    </div>
  );
};

export default TicketsList;