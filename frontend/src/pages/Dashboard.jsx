import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';
import { useAuthStore } from '../store/authStore';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis,
  LineChart, 
  Line, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Cell,
  Legend
} from 'recharts';
import { 
  ShieldAlert, 
  TrendingUp, 
  Play, 
  CheckCircle2, 
  Inbox, 
  Calendar,
  Plus,
  Clock,
  Download, // Icono para el boton de exportar
  Filter
} from 'lucide-react';

const Dashboard = () => {
  const navigate = useNavigate();
  const { role } = useAuthStore();

  // Estados de métricas
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  
  // Estados de riesgo de abandono
  const [churnRiskOrganizations, setChurnRiskOrganizations] = useState([]);
  const [loadingChurn, setLoadingChurn] = useState(true);
  const [errorChurn, setErrorChurn] = useState('');

  // Estados de proyección de capacidad
  const [historicalMonths, setHistoricalMonths] = useState(3);
  const [capacityProjectionData, setCapacityProjectionData] = useState([]);
  const [hiringAlerts, setHiringAlerts] = useState([]);
  const [loadingCapacity, setLoadingCapacity] = useState(true);
  const [errorCapacity, setErrorCapacity] = useState('');
  // Estado del período de fecha (valor predeterminado AAAA-MM para el mes actual)
  const [period, setPeriod] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });

  // Organizaciones por estados de recuento de entradas
  const [ticketsMin, setTicketsMin] = useState('');
  const [ticketsMax, setTicketsMax] = useState('');
  const [filteredOrgs, setFilteredOrgs] = useState([]);
  const [loadingOrgs, setLoadingOrgs] = useState(false);
  const [errorOrgs, setErrorOrgs] = useState('');

  // 1. Verificación de RBAC: asegúrese de que SÓLO los roles de Administrador puedan ver este panel
  const isAuthorized = role === 'Administrador';

  useEffect(() => {
    if (!isAuthorized) {
      setLoadingChurn(false); // Si no está autorizado, no hay riesgo de abandonar que cargar
      setLoadingCapacity(false); // Si no está autorizado, no hay capacidad que cargar
      setLoading(false);
      return;
    }

    const fetchMetrics = async (silent = false) => {
      try {
        if (!silent) setLoading(true);
        const response = await api.get(`/dashboard/metrics?period=${period}`);
        setMetrics(response.data);
        setErrorMsg('');
      } catch (err) {
        console.error('Error fetching dashboard metrics:', err);
        setErrorMsg('Error al recuperar las estadísticas del panel. Intente nuevamente.');
      } finally {
        if (!silent) setLoading(false);
      }
    };

    const fetchChurnRisk = async (silent = false) => {
      try {
        if (!silent) setLoadingChurn(true);
        const response = await api.get('/analytics/churn-risk');
        const mapped = (response.data || []).map(org => ({
          organization_name: org.organization_name || 'Desconocida',
          organization_rut: org.customer_id,
          sla_violation_percentage: Math.round((org.tasa_violacion_sla || 0) * 100),
          average_survey_rating: org.satisfaccion_promedio !== null && org.satisfaccion_promedio !== undefined 
            ? org.satisfaccion_promedio.toFixed(1) 
            : 'N/A',
          riesgo_inminente: org.riesgo_inminente_cancelacion,
          organization_email: org.organization_email || 'contacto@empresa.cl'
        }));
        setChurnRiskOrganizations(mapped);
        setErrorChurn('');
      } catch (err) {
        console.error('Error fetching churn risk organizations:', err);
        setErrorChurn('Error al recuperar las organizaciones en riesgo de churn.');
      } finally {
        if (!silent) setLoadingChurn(false);
      }
    };

    const fetchCapacityProjection = async (silent = false) => {
      try {
        if (!silent) setLoadingCapacity(true);
        const response = await api.get(`/analytics/capacity-projection?rango_meses=${historicalMonths}`);
        const projections = response.data.projections || [];

        // 1. Procesar alertas de contratación
        const alerts = [];
        projections.forEach(proj => {
          if (proj.alerta) {
            alerts.push({
              categoria: proj.categoria,
              reason: `${proj.categoria}: ${proj.alerta}`
            });
          }
        });
        setHiringAlerts(alerts);

        // 2. Mapear proyecciones de grupo a valores mensuales cronológicos para Recharts
        const monthsMap = {};
        projections.forEach(proj => {
          const category = proj.categoria;
          const history = proj.history || [];
          history.forEach(item => {
            const ym = item.year_month;
            if (!monthsMap[ym]) {
              monthsMap[ym] = { month: ym };
            }
            monthsMap[ym][`${category}_incidents`] = item.count;
            
            // Valores de capacidad operativa base por especialidad
            const capacityBaselines = {
              'Hardware': 10,
              'Software': 15,
              'Redes': 8
            };
            monthsMap[ym][`${category}_capacity`] = capacityBaselines[category] || 10;
          });
        });

        const formattedData = Object.values(monthsMap).sort((a, b) => a.month.localeCompare(b.month));
        setCapacityProjectionData(formattedData);
        setErrorCapacity('');
      } catch (err) {
        console.error('Error fetching capacity projection:', err);
        setErrorCapacity('Error al recuperar la proyección de capacidad.');
      } finally {
        if (!silent) setLoadingCapacity(false);
      }
    };

    // Primera carga
    fetchMetrics(false);
    fetchChurnRisk(false);
    fetchCapacityProjection(false);

    // Configurar el intervalo de actualización automática (cada 60 segundos)
    const intervalId = setInterval(() => {
      fetchMetrics(true);
      fetchChurnRisk(true);
      fetchCapacityProjection(true);
    }, 60000);

    return () => {
      clearInterval(intervalId);
    };
  }, [isAuthorized, period, historicalMonths]); // Añadir meses historicos a las dependencias

  const fetchOrgsByTicketCount = async () => {
    if (!isAuthorized) return;
    try {
      setLoadingOrgs(true);
      setErrorOrgs('');
      const params = {};
      if (ticketsMin !== '') params.tickets_min = parseInt(ticketsMin, 10);
      if (ticketsMax !== '') params.tickets_max = parseInt(ticketsMax, 10);
      const response = await api.get('/dashboard/organizations-by-ticket-count', { params });
      setFilteredOrgs(response.data || []);
    } catch (err) {
      console.error('Error fetching organizations by ticket count:', err);
      setErrorOrgs('Error al recuperar la segmentación de organizaciones.');
    } finally {
      setLoadingOrgs(false);
    }
  };

  useEffect(() => {
    if (isAuthorized) {
      const fetchInitialOrgs = async () => {
        try {
          setLoadingOrgs(true);
          const response = await api.get('/dashboard/organizations-by-ticket-count');
          setFilteredOrgs(response.data || []);
        } catch (err) {
          console.error(err);
          setErrorOrgs('Error al recuperar la segmentación de organizaciones.');
        } finally {
          setLoadingOrgs(false);
        }
      };
      fetchInitialOrgs();
    }
  }, [isAuthorized]);

  if (loading || loadingChurn || loadingCapacity) { // Cargador visual combinado con capacidad
    return (
      <div className="flex flex-col items-center justify-center w-full h-64 gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
        <span className="text-sm tracking-wider text-white/40">Cargando estadísticas...</span>
      </div>
    );
  }

  // Manejar bloqueo de roles no autorizados
  if (!isAuthorized) {
    return (
      <div className="max-w-md p-8 mx-auto mt-16 space-y-4 text-center border rounded-md bg-red-950/10 border-red-500/10">
        <div className="flex justify-center">
          <ShieldAlert className="text-red-500 h-14 w-14" />
        </div>
        <h2 className="text-lg font-bold tracking-wider text-white uppercase">Acceso Denegado</h2>
        <p className="text-xs leading-relaxed text-white/40">
          Usted posee el rol de <strong className="text-red-400">{role}</strong>. Esta sección analítica contiene información financiera y gerencial sensible reservada estrictamente para **Administradores**.
        </p>
      </div>
    );
  }

  if (errorMsg || !metrics || errorChurn || errorCapacity) { // Mostrar error si hay en métricas, abandono o capacidad
    return (
      <div className="max-w-xl p-8 mx-auto text-center border rounded bg-orange-950/10 border-orange-500/10">
        <span className="text-xs font-semibold text-orange-400">{errorMsg || errorChurn || errorCapacity || 'No se pudieron recuperar las métricas o alertas.'}</span>
      </div>
    );
  }

  const isRangeInvalid = ticketsMin !== '' && ticketsMax !== '' && parseInt(ticketsMax, 10) < parseInt(ticketsMin, 10);

  const statusCounts = metrics.status_counts || {};
  const criticalSlaCount = metrics.critical_sla_count || 0;
  const recentLogs = metrics.recent_logs || [];

  // Cálculos de estadísticas agregadas
  const totalMonthTickets = Object.values(statusCounts).reduce((acc, curr) => acc + curr, 0);
  const openCount = statusCounts['Abierto'] || 0;
  const inProgressCount = statusCounts['En Proceso'] || 0;
  const resolvedCount = (statusCounts['Resuelto'] || 0) + (statusCounts['Cerrado'] || 0);

  // Mapeo de carga útil de Recharts
  const chartData = Object.entries(statusCounts).map(([name, value]) => ({
    name,
    value
  }));

  // Mapeo de colores del tema estatal
  const STATE_COLORS = {
    'Abierto': '#94a3b8',       // Gris/Pizarra
    'Asignado': '#0066FF',      // azul tecnológico
    'En Proceso': '#fbbf24',    // Ámbar
    'En Espera': '#c084fc',     // Púrpura
    'Resuelto': '#10b981',      // Esmeralda
    'Cerrado': '#059669'       // esmeralda oscura
  };

  // Colores para las especialidades en el gráfico de capacidad.
  const SPECIALTY_COLORS = {
    'Hardware': '#00D2FF',
    'Software': '#10b981',
    'Redes': '#fbbf24',
  };
  // Función para exportar contactos a CSV
  const exportContacts = (organization) => {
    const csvContent = "data:text/csv;charset=utf-8,"
      + "Nombre de la Organización,RUT,Email de Contacto\n"
      + `${organization.organization_name},${organization.organization_rut},${organization.organization_email}\n`;

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `contactos_contencion_${organization.organization_rut}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-8">
      
      {/* título */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-wide text-white">Panel Analítico Gerencial</h2>
          <p className="mt-1 text-xs text-white/40">Métricas clave agregadas de tickets creados en el período seleccionado.</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Botón de acción rápida */}
          <button
            onClick={() => navigate('/tickets/new')}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold rounded transition duration-200 uppercase tracking-wider shadow-[0_0_10px_rgba(0,102,255,0.15)]"
            title="Crear un ticket de soporte inmediatamente"
          >
            <Plus className="w-4 h-4 animate-pulse" />
            <span>Ticket Rápido</span>
          </button>

          <div className="flex items-center gap-2 bg-[#22262B] px-3 py-1.5 rounded border border-white/10 text-xs text-white">
            <Calendar className="h-4 w-4 text-[#00D2FF]" />
            <input
              type="month"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="text-xs font-semibold text-white uppercase bg-transparent border-none cursor-pointer focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* Cuadrícula de resumen de estadísticas de 5 cartas. */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        
        {/* Tarjeta Total Entradas */}
        <div className="p-4 bg-white/5 border border-white/5 hover:border-[#00D2FF]/20 rounded-md transition duration-300 space-y-2">
          <div className="flex items-center justify-between text-white/40">
            <span className="text-[10px] font-bold uppercase tracking-wider">Tickets del Mes</span>
            <TrendingUp className="h-5 w-5 text-[#00D2FF]" />
          </div>
          <p className="text-3xl font-extrabold text-white">{totalMonthTickets}</p>
          <p className="text-[10px] text-white/30">Total creados en el mes</p>
        </div>

        {/* Tarjeta de entradas abiertas */}
        <div className="p-4 space-y-2 transition duration-300 border rounded-md bg-white/5 border-white/5 hover:border-slate-500/20">
          <div className="flex items-center justify-between text-white/40">
            <span className="text-[10px] font-bold uppercase tracking-wider">Pendientes de Asignar</span>
            <Inbox className="w-5 h-5 text-slate-400" />
          </div>
          <p className="text-3xl font-extrabold text-white">{openCount}</p>
          <p className="text-[10px] text-white/30">Estado: Abierto</p>
        </div>

        {/* Tarjeta de entradas en curso */}
        <div className="p-4 space-y-2 transition duration-300 border rounded-md bg-white/5 border-white/5 hover:border-amber-500/20">
          <div className="flex items-center justify-between text-white/40">
            <span className="text-[10px] font-bold uppercase tracking-wider">En Atención</span>
            <Play className="w-5 h-5 text-amber-400" />
          </div>
          <p className="text-3xl font-extrabold text-white">{inProgressCount}</p>
          <p className="text-[10px] text-white/30">Estado: En Proceso</p>
        </div>

        {/* Tarjeta de Tickets Resueltos/Cerrados */}
        <div className="p-4 space-y-2 transition duration-300 border rounded-md bg-white/5 border-white/5 hover:border-emerald-500/20">
          <div className="flex items-center justify-between text-white/40">
            <span className="text-[10px] font-bold uppercase tracking-wider">Solucionados</span>
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
          <p className="text-3xl font-extrabold text-white">{resolvedCount}</p>
          <p className="text-[10px] text-white/30">Estado: Resueltos / Cerrados</p>
        </div>

        {/* Tarjeta de tickets críticos SLA */}
        <div className={`p-4 border rounded-md transition duration-300 space-y-2 ${
          criticalSlaCount > 0 
            ? 'bg-red-950/20 border-red-500/30 hover:border-red-500 animate-pulse' 
            : 'bg-white/5 border-white/5 hover:border-red-500/20'
        }`}>
          <div className="flex items-center justify-between text-white/40">
            <span className="text-[10px] font-bold uppercase tracking-wider">SLA Crítico (&lt;1h)</span>
            <Clock className={`h-5 w-5 ${criticalSlaCount > 0 ? 'text-red-500' : 'text-white/45'}`} />
          </div>
          <p className={`text-3xl font-extrabold ${criticalSlaCount > 0 ? 'text-red-400' : 'text-white'}`}>{criticalSlaCount}</p>
          <p className="text-[10px] text-white/30">Tickets por vencer</p>
        </div>

      </div>

      {/* Sección de gráfico principal */}
      <div className="p-6 bg-[#22262B]/20 border border-white/5 rounded-md space-y-6">
        <div>
          <h3 className="text-xs font-bold tracking-wider uppercase text-white/40">Distribución de Incidentes por Estado</h3>
          <p className="text-[10px] text-white/30 mt-1">Recuentos individuales por etapa del ciclo de vida.</p>
        </div>

        <div className="w-full bg-transparent h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart 
              data={chartData} 
              margin={{ top: 20, right: 10, left: -20, bottom: 5 }}
            >
              <CartesianGrid 
                strokeDasharray="3 3" 
                stroke="rgba(255,255,255,0.05)" 
                vertical={false} 
              />
              <XAxis 
                dataKey="name" 
                stroke="rgba(255,255,255,0.4)" 
                fontSize={11} 
                tickLine={false} 
                axisLine={false} 
              />
              <YAxis 
                stroke="rgba(255,255,255,0.4)" 
                fontSize={11} 
                tickLine={false} 
                axisLine={false} 
                allowDecimals={false}
              />
              <Tooltip 
                cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                contentStyle={{ 
                  backgroundColor: '#22262B', 
                  borderColor: 'rgba(255,255,255,0.1)', 
                  borderRadius: '4px',
                  color: '#ffffff'
                }} 
                labelStyle={{ fontSize: '11px', fontWeight: 'bold', color: '#00D2FF' }}
                itemStyle={{ fontSize: '11px', color: '#ffffff' }}
              />
              <Bar 
                dataKey="value" 
                radius={[4, 4, 0, 0]}
                barSize={50}
              >
                {chartData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={STATE_COLORS[entry.name] || '#0066FF'} 
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      {/* Feed de Actividad Reciente (Auditoría) */}
      <div className="p-6 bg-[#22262B]/20 border border-white/5 rounded-md space-y-4">
        <div>
          <h3 className="text-xs font-bold tracking-wider uppercase text-white/40">Feed de Actividad Reciente</h3>
          <p className="text-[10px] text-white/30 mt-1">Últimos eventos registrados en la bitácora de auditoría inmutable.</p>
        </div>

        {recentLogs.length === 0 ? (
          <p className="py-2 text-xs text-white/30">No se han registrado transiciones recientes en este período.</p>
        ) : (
          <div className="space-y-3.5">
            {recentLogs.map((log, index) => (
              <div key={log._id || index} className="flex items-start gap-3 text-xs leading-relaxed border-l-2 border-[#00D2FF]/20 pl-4 ml-1 relative">
                {/* Nodo de círculo de línea de tiempo */}
                <div className="absolute -left-[5px] top-1.5 w-2 h-2 rounded-full bg-[#00D2FF]" />
                
                <div className="flex-1 space-y-1">
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="font-semibold text-white/70 font-mono text-[9px] bg-white/5 px-1.5 py-0.5 rounded border border-white/5">
                      {log.id_ticket || (log.ticket_id ? `TK-${log.ticket_id.substring(Math.max(0, log.ticket_id.length - 6)).toUpperCase()}` : "TK-DESCONOCIDO")}
                    </span>
                    <span className="text-white/30">
                      {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </div>
                  <p className="text-white/80">
                    {log.accion ? (
                      <>
                        {log.accion}: <strong className="text-amber-400/90">{log.valor_anterior || 'N/A'}</strong> a <strong className="text-emerald-400">{log.nuevo_valor || 'N/A'}</strong>
                      </>
                    ) : (
                      <>
                        Tránsito de estado de <strong className="text-amber-400/90">{log.estado_anterior || 'N/A'}</strong> a <strong className="text-emerald-400">{log.estado_nuevo || 'N/A'}</strong>
                      </>
                    )}
                  </p>
                  <p className="text-[10px] text-white/30">Origen IP: {log.ip_origen}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Panel de Proyección de Capacidad */}
      <div className="p-6 bg-[#22262B]/20 border border-white/5 rounded-md space-y-4">
        <div>
          <h3 className="text-xs font-bold tracking-wider uppercase text-white/40">Proyección de Capacidad Técnica</h3>
          <p className="text-[10px] text-white/30 mt-1">Tendencias de incidentes vs. capacidad resolutiva por especialidad.</p>
        </div>

        <div className="flex items-center gap-2 mb-4">
          <label htmlFor="historicalMonths" className="text-xs font-semibold text-white/40">Histórico (Meses):</label>
          <input
            type="number"
            id="historicalMonths"
            min="3"
            value={historicalMonths}
            onChange={(e) => setHistoricalMonths(Math.max(3, parseInt(e.target.value) || 3))}
            className="w-20 px-2 py-1 bg-[#22262B] text-white text-xs rounded border border-white/10 focus:outline-none focus:border-[#00D2FF]"
            disabled={loadingCapacity}
          />
        </div>

        {loadingCapacity && (
          <div className="flex flex-col items-center justify-center w-full h-40 gap-3">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
            <span className="text-xs tracking-wider text-white/40">Calculando proyección de capacidad...</span>
          </div>
        )}

        {errorCapacity && (
          <div className="p-4 text-center border rounded bg-orange-950/10 border-orange-500/10">
            <span className="text-xs font-semibold text-orange-400">{errorCapacity}</span>
          </div>
        )}

        {hiringAlerts.length > 0 && !loadingCapacity && (
          <div className="space-y-2">
            {hiringAlerts.map((alert, index) => (
              <div key={index} className="flex items-center gap-3 p-3 text-xs font-semibold text-red-400 border rounded-md border-red-500/20 bg-red-950/15 animate-pulse">
                <ShieldAlert className="w-4 h-4 text-red-500" />
                <span>¡ALERTA DE CONTRATACIÓN! {alert.reason}</span>
              </div>
            ))}
          </div>
        )}

        {capacityProjectionData.length === 0 && !loadingCapacity && !errorCapacity ? (
          <p className="py-2 text-xs text-white/30">No hay datos de proyección de capacidad disponibles.</p>
        ) : (
          <div className="w-full bg-transparent h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={capacityProjectionData}
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis
                  dataKey="month"
                  stroke="rgba(255,255,255,0.4)"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke="rgba(255,255,255,0.4)"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#22262B',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderRadius: '4px',
                    color: '#ffffff'
                  }}
                  labelStyle={{ fontSize: '11px', fontWeight: 'bold', color: '#00D2FF' }}
                  itemStyle={{ fontSize: '11px', color: '#ffffff' }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', color: 'rgba(255,255,255,0.6)', paddingTop: '10px' }} />

                {Object.keys(SPECIALTY_COLORS).map(specialty => (
                  <React.Fragment key={specialty}>
                    <Line
                      type="monotone"
                      dataKey={`${specialty}_incidents`}
                      stroke={SPECIALTY_COLORS[specialty]}
                      name={`${specialty} (Incidentes)`}
                      strokeWidth={2}
                    />
                    <Line
                      type="monotone"
                      dataKey={`${specialty}_capacity`}
                      stroke={SPECIALTY_COLORS[specialty]}
                      name={`${specialty} (Capacidad)`}
                      strokeDasharray="5 5"
                      strokeWidth={1}
                    />
                  </React.Fragment>
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Panel Analítico Predictivo de Alerta Temprana de Churn */}
      <div className="p-6 bg-[#22262B]/20 border border-white/5 rounded-md space-y-4">
        <div>
          <h3 className="text-xs font-bold tracking-wider uppercase text-white/40">Alerta Temprana de Churn</h3>
          <p className="text-[10px] text-white/30 mt-1">Organizaciones con riesgo inminente de cancelación de servicio.</p>
        </div>

        {errorChurn && (
          <div className="p-4 text-center border rounded bg-orange-950/10 border-orange-500/10">
            <span className="text-xs font-semibold text-orange-400">{errorChurn}</span>
          </div>
        )}

        {churnRiskOrganizations.length === 0 && !loadingChurn && !errorChurn ? (
          <p className="py-2 text-xs text-white/30">No se detectaron organizaciones con riesgo de churn en los últimos 14 días.</p>
        ) : (
          <div className="w-full overflow-x-auto rounded bg-[#22262B]/30 border border-white/5">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/5 bg-slate-900">
                  <th className="px-6 py-3 text-xs font-semibold tracking-wider text-slate-400 bg-slate-900">ORGANIZACIÓN</th>
                  <th className="px-6 py-3 text-xs font-semibold tracking-wider text-slate-400 bg-slate-900">RUT</th>
                  <th className="px-6 py-3 text-xs font-semibold tracking-wider text-slate-400 bg-slate-900">SLA VIOLADO (%)</th>
                  <th className="px-6 py-3 text-xs font-semibold tracking-wider text-slate-400 bg-slate-900">SATISFACCIÓN PROMEDIO</th>
                  <th className="px-6 py-3 text-xs font-semibold tracking-wider text-right text-slate-400 bg-slate-900">ACCIONES</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {churnRiskOrganizations.map((org, index) => (
                  <tr key={org.organization_id || index} className="transition duration-150 hover:bg-white/5">
                    <td className="px-6 py-3 text-sm font-semibold text-white/90">
                      {org.organization_name}
                      {org.riesgo_inminente && (
                        // Bandera de Alerta Visual
                        <span className="ml-2 inline-flex items-center rounded-full bg-red-900/30 px-2 py-0.5 text-[9px] font-bold text-red-400 animate-pulse border border-red-500/20">
                          <ShieldAlert className="w-3 h-3 mr-1" /> RIESGO INMINENTE
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-sm font-semibold text-[#00D2FF] font-mono">{org.organization_rut}</td>
                    <td className={`px-6 py-3 text-sm font-bold ${org.sla_violation_percentage > 15 ? 'text-red-400' : 'text-white/80'}`}>{org.sla_violation_percentage}%</td>
                    <td className="px-6 py-3 text-sm font-bold text-orange-400">
                      {org.average_survey_rating === 'N/A' ? 'N/A ⭐' : `${org.average_survey_rating} ★`}
                    </td>
                    <td className="px-6 py-3 text-sm text-right">
                      {/* Botón de Exportar Contactos */}
                      <button
                        onClick={() => exportContacts(org)}
                        className="inline-flex items-center gap-1 p-1 transition duration-150 rounded text-white/45 hover:text-emerald-500 hover:bg-emerald-500/10"
                        title="Exportar contactos de contención"
                      >
                        <Download className="w-4 h-4" />
                        <span className="text-xs font-semibold">Exportar</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Panel de Segmentación de Organizaciones por Tickets */}
      <div className="p-6 bg-[#22262B]/20 border border-white/5 rounded-md space-y-4">
        <div>
          <h3 className="text-xs font-bold tracking-wider uppercase text-white/40">Segmentación de Organizaciones por Tickets</h3>
          <p className="text-[10px] text-white/30 mt-1">Busque y filtre organizaciones según el rango de tickets acumulados.</p>
        </div>

        {/* Panel Filtrante Contenedor Flex con Altura Homologada h-10 */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 h-10">
            <span className="text-[10px] text-white/40 uppercase font-bold tracking-wider">Mínimo:</span>
            <input
              type="number"
              min="0"
              placeholder="0"
              value={ticketsMin}
              onChange={(e) => setTicketsMin(e.target.value)}
              className="w-24 h-10 px-3 bg-[#22262B]/30 text-white text-xs border border-white/10 rounded focus:outline-none focus:border-[#00D2FF] transition duration-200"
            />
          </div>

          <div className="flex items-center gap-2 h-10">
            <span className="text-[10px] text-white/40 uppercase font-bold tracking-wider">Máximo:</span>
            <input
              type="number"
              min="0"
              placeholder="100"
              value={ticketsMax}
              onChange={(e) => setTicketsMax(e.target.value)}
              className={`w-24 h-10 px-3 bg-[#22262B]/30 text-white text-xs border rounded focus:outline-none focus:border-[#00D2FF] transition duration-200 ${
                isRangeInvalid ? 'border-red-500/50 focus:border-red-500' : 'border-white/10'
              }`}
            />
          </div>

          <div className="flex flex-col justify-center h-10">
            <button
              onClick={fetchOrgsByTicketCount}
              disabled={loadingOrgs || isRangeInvalid}
              className="h-10 px-4 flex items-center justify-center gap-2 bg-[#0066FF] hover:bg-[#00D2FF] disabled:bg-white/5 disabled:border-white/10 disabled:text-white/20 text-white text-xs font-bold rounded-lg transition-all duration-200 border border-transparent shadow-[0_0_10px_rgba(0,102,255,0.15)] shrink-0 cursor-pointer"
              title="Filtrar organizaciones"
            >
              <Filter className="w-4 h-4" />
              <span>Filtrar</span>
            </button>
          </div>

          {isRangeInvalid && (
            <div className="flex items-center h-10 text-[10px] text-red-400 font-semibold">
              <span>El máximo no puede ser menor que el mínimo.</span>
            </div>
          )}
        </div>

        {/* Sub-tabla de resultados */}
        {errorOrgs && (
          <div className="p-4 text-center border rounded bg-orange-950/10 border-orange-500/10">
            <span className="text-xs font-semibold text-orange-400">{errorOrgs}</span>
          </div>
        )}

        {loadingOrgs ? (
          <div className="flex flex-col items-center justify-center w-full h-40 gap-3">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
            <span className="text-xs tracking-wider text-white/40">Segmentando organizaciones...</span>
          </div>
        ) : filteredOrgs.length === 0 ? (
          <p className="py-2 text-xs text-white/30">No se encontraron organizaciones en el rango especificado.</p>
        ) : (
          <div className="w-full overflow-x-auto rounded bg-[#22262B]/30 border border-white/5">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/5 bg-slate-900">
                  <th className="px-6 py-3 text-xs font-semibold tracking-wider text-slate-400 bg-slate-900">ORGANIZACIÓN</th>
                  <th className="px-6 py-3 text-xs font-semibold tracking-wider text-slate-400 bg-slate-900">RUT</th>
                  <th className="px-6 py-3 text-xs font-semibold tracking-wider text-slate-400 bg-slate-900">CONTRATO</th>
                  <th className="px-6 py-3 text-xs font-semibold tracking-wider text-slate-400 bg-slate-900">INDUSTRIA</th>
                  <th className="px-6 py-3 text-xs font-semibold tracking-wider text-right text-slate-400 bg-slate-900">TICKETS ACUMULADOS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredOrgs.map((org, index) => (
                  <tr key={org._id || index} className="transition duration-150 hover:bg-white/5">
                    <td className="px-6 py-3 text-sm font-semibold text-white/90">{org.name}</td>
                    <td className="px-6 py-3 text-sm font-semibold text-[#00D2FF] font-mono">{org.rut}</td>
                    <td className="px-6 py-3 text-sm text-white/70">
                      <span className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-wider ${
                        org.tier_contractual === 'Oro' 
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : org.tier_contractual === 'Plata'
                            ? 'bg-slate-300/10 text-slate-300 border border-slate-300/20'
                            : 'bg-orange-700/10 text-orange-400 border border-orange-700/20'
                      }`}>
                        {org.tier_contractual}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-sm text-white/50">{org.industria || 'N/A'}</td>
                    <td className="px-6 py-3 text-sm font-bold text-right text-emerald-400 font-mono">{org.tickets_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;