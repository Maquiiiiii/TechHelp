import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../utils/api';
import { useAuthStore } from '../store/authStore';
import { 
  Paperclip, 
  Send, 
  Lock, 
  AlertCircle, 
  CheckCircle2, 
  Pause, 
  Play, 
  ArrowLeft,
  Clock, 
  User, 
  Download,
  AlertTriangle,
  FolderOpen,
  EyeOff,
  Star
} from 'lucide-react';

const TicketDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { role } = useAuthStore();

  // Estado central
  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  
  // Estados de interacción
  const [newComment, setNewComment] = useState('');
  const [isInternalComment, setIsInternalComment] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [submittingStatus, setSubmittingStatus] = useState(false);
  const [actionError, setActionError] = useState('');

  // Formas de máquina de estados
  const [showPauseInput, setShowPauseInput] = useState(false);
  const [justificacionPausa, setJustificacionPausa] = useState('');
  
  const [showResolveInput, setShowResolveInput] = useState(false);
  const [comentarioSolucion, setComentarioSolucion] = useState('');

  // Estados de retroalimentación
  const [feedbackRating, setFeedbackRating] = useState(0);
  const [hoverFeedbackRating, setHoverFeedbackRating] = useState(0);
  const [feedbackComments, setFeedbackComments] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [submittedFeedback, setSubmittedFeedback] = useState(false);
  const [feedbackError, setFeedbackError] = useState('');

  const handleSubmitFeedback = async () => {
    if (feedbackRating < 1 || feedbackRating > 5) {
      setFeedbackError('Por favor seleccione una calificación entre 1 y 5.');
      return;
    }
    setSubmittingFeedback(true);
    setFeedbackError('');
    try {
      await api.post(`/tickets/${id}/feedback`, {
        valoracion: feedbackRating,
        comentarios: feedbackComments || null
      });
      setSubmittedFeedback(true);
    } catch (err) {
      console.error('Error submitting feedback:', err);
      const msg = err.response?.data?.detail || 'Error al enviar la reseña. Intente nuevamente.';
      setFeedbackError(msg);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  // Obtener detalles del billete
  const fetchTicketDetails = async () => {
    try {
      const response = await api.get(`/tickets/${id}`);
      setTicket(response.data);
      setErrorMsg('');
    } catch (err) {
      console.error('Error fetching ticket:', err);
      setErrorMsg('No se pudo cargar el detalle del ticket.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTicketDetails();
  }, [id]);

  // Manejar el envío de nuevos comentarios (&)
  const handleCommentSubmit = async (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;

    try {
      const response = await api.post(`/tickets/${id}/comments`, {
        texto: newComment,
        es_interno: isInternalComment
      });
      
      let updatedTicket = response.data;

      // Reanudación del SLA: Si el ticket era "En Espera" y el autor es un "Cliente",
      // reanuda SLA volviendo a "En Proceso".
      if (ticket.status === 'En Espera' && role === 'Cliente') {
        const transitionRes = await api.put(`/tickets/${id}/status`, {
          status: 'En Proceso',
          version: updatedTicket.__v
        });
        updatedTicket = transitionRes.data;
      }

      setTicket(updatedTicket);
      setNewComment('');
      setIsInternalComment(false);
    } catch (err) {
      console.error('Error post comment:', err);
      setActionError('Error al registrar el comentario.');
    }
  };

  // Manejar la carga de archivos adjuntos
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setActionError('');

    // Validaciones del lado del cliente (solo PDF, PNG, JPG)
    const allowedExtensions = ['pdf', 'png', 'jpg'];
    const fileExtension = file.name.split('.').pop().toLowerCase();
    
    if (!allowedExtensions.includes(fileExtension)) {
      setActionError('Formato no permitido');
      e.target.value = '';
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setActionError('El archivo supera los 5MB');
      e.target.value = '';
      return;
    }

    setUploadingFile(true);
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post(`/tickets/${id}/attachments`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setTicket(response.data);
    } catch (err) {
      console.error('Error uploading file:', err);
      setActionError(err.response?.data?.detail || 'Error al subir el archivo adjunto.');
    } finally {
      setUploadingFile(false);
      // Restablecer valor de entrada
      e.target.value = '';
    }
  };

  // Manejar transiciones de máquinas de estados (, , )
  const handleStatusTransition = async (targetStatus, extraPayload = {}) => {
    setSubmittingStatus(true);
    setActionError('');
    
    try {
      const response = await api.put(`/tickets/${id}/status`, {
        status: targetStatus,
        version: ticket.__v, // validación OCC
        ...extraPayload
      });
      
      setTicket(response.data);
      
      // Restablecer formularios
      setShowPauseInput(false);
      setJustificacionPausa('');
      setShowResolveInput(false);
      setComentarioSolucion('');
    } catch (err) {
      console.error('Error updating status:', err);
      const msg = err.response?.data?.detail || 'Error al actualizar el estado del ticket.';
      setActionError(msg);
    } finally {
      setSubmittingStatus(false);
    }
  };

  // Manejar la asignación automática de tickets abiertos
  const handleAutoAssign = async () => {
    setSubmittingStatus(true);
    setActionError('');
    try {
      const response = await api.post(`/tickets/${id}/auto-assign`, {
        version: ticket.__v // validación OCC
      });
      setTicket(response.data);
    } catch (err) {
      console.error('Error auto assigning ticket:', err);
      const msg = err.response?.data?.detail || 'Error al autoasignar el técnico.';
      setActionError(msg);
    } finally {
      setSubmittingStatus(false);
    }
  };

  // Estilos de ayuda para la insignia de estado
  const getStatusBadgeStyles = (status) => {
    switch (status) {
      case 'Abierto':
        return 'bg-white/10 text-white/80 border border-white/20';
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
        return 'bg-white/5 text-white border border-transparent';
    }
  };

  // Renderizar Skeleton Loader mientras se recupera
  if (loading) {
    return (
      <div className="max-w-6xl mx-auto space-y-6 animate-pulse">
        <div className="h-6 w-24 bg-white/5 rounded"></div>
        <div className="flex justify-between items-center">
          <div className="h-10 w-96 bg-white/5 rounded"></div>
          <div className="h-10 w-24 bg-white/5 rounded"></div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="h-48 bg-white/5 rounded"></div>
            <div className="h-32 bg-white/5 rounded"></div>
            <div className="h-64 bg-white/5 rounded"></div>
          </div>
          <div className="h-96 bg-white/5 rounded"></div>
        </div>
      </div>
    );
  }

  if (errorMsg || !ticket) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <button onClick={() => navigate('/tickets')} className="flex items-center gap-2 text-xs text-white/40 hover:text-white transition duration-200">
          <ArrowLeft className="h-4 w-4" /> Volver al listado
        </button>
        <div className="text-center p-8 bg-orange-950/15 border border-orange-500/10 rounded">
          <span className="text-sm font-semibold text-orange-400">{errorMsg || 'Ticket no encontrado.'}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      
      {/* Navegación y encabezado de código */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <button 
          onClick={() => navigate('/tickets')} 
          className="flex items-center gap-2 text-xs text-white/40 hover:text-white transition duration-200 uppercase tracking-wider font-semibold"
        >
          <ArrowLeft className="h-4 w-4" /> Volver al listado
        </button>
        <span className="text-xs text-white/40 font-mono">
          Creado el: {new Date(ticket.created_at).toLocaleString()}
        </span>
      </div>

      {/* Banner de título principal */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-white/5 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-xl font-bold tracking-widest text-[#00D2FF] font-mono">{ticket.code}</span>
            <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-full ${getStatusBadgeStyles(ticket.status)}`}>
              {ticket.status}
            </span>
          </div>
          <h2 className="text-2xl font-bold text-white mt-2 leading-relaxed">{ticket.title}</h2>
        </div>
      </div>

      {/* Diseño de detalles del cuerpo. */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        
        {/* Columna izquierda: detalles, archivos adjuntos y comentarios */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* Descripción del ticket de lectura en solitario */}
          <div className="bg-[#22262B]/20 border border-white/5 rounded-md p-6 space-y-4">
            <h3 className="text-xs font-bold text-white/40 uppercase tracking-wider">Descripción del Incidente</h3>
            <p className="text-sm leading-relaxed text-white/80 whitespace-pre-wrap">
              {ticket.description}
            </p>
            
            {/* Lista detallada de parámetros horizontales */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 pt-4 border-t border-white/5">
              <div>
                <span className="block text-[10px] text-white/40 uppercase font-semibold">Categoría</span>
                <span className="text-sm font-semibold text-white/80">{ticket.categoria}</span>
              </div>
              <div>
                <span className="block text-[10px] text-white/40 uppercase font-semibold">Prioridad</span>
                <span className="text-sm font-semibold text-white/80">{ticket.prioridad}</span>
              </div>
              <div>
                <span className="block text-[10px] text-white/40 uppercase font-semibold">Cliente RUT</span>
                <span className="text-sm font-semibold text-[#00D2FF] font-mono">{ticket.customer_id}</span>
              </div>
            </div>
          </div>

          {/* Sección de archivos adjuntos */}
          <div className="bg-[#22262B]/20 border border-white/5 rounded-md p-6 space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-xs font-bold text-white/40 uppercase tracking-wider">Archivos Adjuntos</h3>
              <label className={`flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 hover:border-[#00D2FF] hover:text-[#00D2FF] text-xs font-semibold rounded cursor-pointer transition duration-200 ${uploadingFile ? 'opacity-50 cursor-not-allowed' : ''}`}>
                <Paperclip className="h-4 w-4" />
                <span>{uploadingFile ? 'Subiendo...' : 'Adjuntar Evidencia'}</span>
                <input 
                  type="file" 
                  disabled={uploadingFile}
                  onChange={handleFileUpload}
                  className="hidden" 
                  accept=".pdf,.png,.jpg,.jpeg"
                />
              </label>
            </div>

            {/* Lista de archivos adjuntos */}
            {ticket.adjuntos && ticket.adjuntos.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                {ticket.adjuntos.map((url, index) => {
                  const filename = url.split('/').pop() || `Archivo_${index + 1}`;
                  return (
                    <div key={index} className="flex items-center justify-between p-3 bg-white/5 border border-white/5 rounded-md">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <FolderOpen className="h-4 w-4 text-[#00D2FF] shrink-0" />
                        <span className="text-xs text-white/70 truncate">{filename}</span>
                      </div>
                      <a 
                        href={url} 
                        download
                        target="_blank" 
                        rel="noreferrer"
                        className="text-[#00D2FF] hover:text-white transition duration-150"
                        title="Ver o descargar archivo"
                      >
                        <Download className="h-4 w-4" />
                      </a>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-white/30 italic">No hay archivos adjuntos en este ticket.</p>
            )}
          </div>

          {/* Feed de comentarios (&) */}
          <div className="bg-[#22262B]/20 border border-white/5 rounded-md p-6 space-y-6">
            <h3 className="text-xs font-bold text-white/40 uppercase tracking-wider">Historial de Comentarios</h3>

            {/* Hola de conversación */}
            {ticket.comentarios && ticket.comentarios.length > 0 ? (
              <div className="space-y-4 max-h-[350px] overflow-y-auto pr-2">
                {ticket.comentarios
                  .filter(c => !(role === 'Cliente' && c.es_interno))
                  .map((c, index) => {
                    const isIntern = c.es_interno;
                  return (
                    <div 
                      key={index} 
                      className={`p-4 rounded border transition duration-150 ${
                        isIntern 
                          ? 'bg-purple-950/10 border-purple-500/10' 
                          : 'bg-white/5 border-white/5'
                      }`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div className="space-y-0.5">
                          <div className="text-sm font-semibold text-white/90">
                            {c.autor_nombre || c.autor || 'Sistema'}
                          </div>
                          <div className="text-xs text-white/40">
                            {c.autor_email || c.autor || 'sistema@techhelp.cl'} — {c.autor_rol || c.rol_autor || 'Sistema'}
                          </div>
                        </div>
                        {isIntern && (
                          <span className="flex items-center gap-1 text-[9px] text-purple-400 font-bold uppercase tracking-wider select-none">
                            <EyeOff className="h-3 w-3" /> Nota Interna
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-white/80 leading-relaxed break-words mt-3 whitespace-pre-wrap">{c.texto}</p>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-white/30 italic">No se han registrado comentarios públicos ni privados.</p>
            )}

            {/* Agregar formulario de comentarios o banner finalizado */}
            {['Cerrado', 'Rechazado', 'Cancelado'].includes(ticket.status) ? (
              <div className="flex items-center gap-3 p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-md text-xs font-semibold select-none mt-4">
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-500 animate-pulse" />
                <span>Este ticket ha sido finalizado. No se permiten más interacciones.</span>
              </div>
            ) : (
              <form onSubmit={handleCommentSubmit} className="space-y-3 pt-4 border-t border-white/5">
                <div className="relative">
                  <textarea
                    required
                    rows={3}
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    placeholder="Escriba un comentario o nota para el ticket..."
                    className="w-full px-4 py-3 bg-transparent text-[#FFFFFF] placeholder-white/20 border border-white/10 rounded focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-200 text-xs resize-none"
                  />
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  {/* Nota Casilla de verificación de pasante (solo se muestra si es técnico o administrador) */}
                  {(role === 'Tecnico' || role === 'Administrador') ? (
                    <label className="flex items-center gap-2 text-xs text-purple-400 font-semibold cursor-pointer select-none">
                      <input 
                        type="checkbox"
                        checked={isInternalComment}
                        onChange={(e) => setIsInternalComment(e.target.checked)}
                        className="rounded bg-transparent border-purple-500/30 text-purple-600 focus:ring-0 cursor-pointer"
                      />
                      <span>Registrar como Nota Interna (Oculta para clientes)</span>
                    </label>
                  ) : (
                    <div /> // bloque espaciador
                  )}

                  <button
                    type="submit"
                    className="flex items-center justify-center gap-2 px-4 py-2 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 uppercase"
                  >
                    <Send className="h-3.5 w-3.5" />
                    <span>Comentar</span>
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Tarea 1: Interfaz de Reseña Exclusiva para Clientes */}
          {role === 'Cliente' && ticket.status === 'Cerrado' && !ticket.feedback_submitted && !submittedFeedback && (
            <div className="bg-[#22262B]/20 border border-[#00D2FF]/20 rounded-md p-6 space-y-4 mt-6">
              <div className="border-b border-white/5 pb-2">
                <h3 className="text-xs font-bold text-[#00D2FF] uppercase tracking-wider">Calificar Servicio</h3>
                <p className="text-[10px] text-white/40">Su opinión nos ayuda a mantener y mejorar la calidad del soporte.</p>
              </div>

              {feedbackError && (
                <div className="p-2.5 bg-red-950/15 border border-red-500/10 rounded text-center text-[11px] text-red-400">
                  {feedbackError}
                </div>
              )}

              <div className="space-y-4">
                {/* Selector de calificación de estrellas */}
                <div className="flex flex-col items-center gap-2">
                  <span className="text-[10px] font-semibold text-white/50 uppercase tracking-wider">Valoración *</span>
                  <div className="flex items-center gap-1.5">
                    {[1, 2, 3, 4, 5].map((index) => {
                      const active = index <= (hoverFeedbackRating || feedbackRating);
                      return (
                        <button
                          key={index}
                          type="button"
                          disabled={submittingFeedback}
                          onClick={() => setFeedbackRating(index)}
                          onMouseEnter={() => setHoverFeedbackRating(index)}
                          onMouseLeave={() => setHoverFeedbackRating(0)}
                          className="p-0.5 hover:scale-110 transition duration-150 transform focus:outline-none"
                        >
                          <Star 
                            className={`h-7 w-7 ${
                              active 
                                ? 'text-yellow-400 fill-yellow-400 filter drop-shadow-[0_0_6px_rgba(250,204,21,0.3)]' 
                                : 'text-white/20'
                            }`} 
                          />
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Área de texto de comentarios */}
                <div className="space-y-1.5">
                  <label className="block text-[10px] font-bold text-white/50 uppercase tracking-wider">
                    Comentarios (Opcional)
                  </label>
                  <textarea
                    rows={3}
                    disabled={submittingFeedback}
                    value={feedbackComments}
                    onChange={(e) => setFeedbackComments(e.target.value)}
                    placeholder="Escriba aquí sus comentarios sobre el servicio..."
                    className="w-full px-3 py-2 bg-transparent text-white placeholder-white/20 border border-white/10 rounded focus:outline-none focus:border-[#00D2FF] text-xs resize-none"
                  />
                </div>

                <button
                  type="button"
                  onClick={handleSubmitFeedback}
                  disabled={submittingFeedback || feedbackRating === 0}
                  className="w-full py-2.5 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-[11px] font-bold tracking-wider rounded transition duration-200 uppercase disabled:opacity-40 shadow-[0_0_12px_rgba(0,102,255,0.15)]"
                >
                  {submittingFeedback ? 'Enviando...' : 'Enviar Reseña'}
                </button>
              </div>
            </div>
          )}

          {submittedFeedback && (
            <div className="bg-emerald-950/10 border border-emerald-500/10 rounded-md p-6 space-y-2 mt-6 text-center">
              <CheckCircle2 className="h-8 w-8 text-emerald-400 mx-auto" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">¡Gracias por calificar!</h3>
              <p className="text-[10px] text-white/60">Su retroalimentación ha sido registrada exitosamente.</p>
            </div>
          )}

        </div>

        {/* Columna derecha: Acciones y metainformación (administración de máquinas de estado) */}
        <div className="space-y-6">
          
          {/* Tarjeta de acciones de la máquina de estados */}
          <div className="bg-[#22262B]/20 border border-white/5 rounded-md p-6 space-y-4">
            <h3 className="text-xs font-bold text-white/40 uppercase tracking-wider">Acciones Disponibles</h3>
            
            {/* Notificaciones de errores para operaciones. */}
            {actionError && (
              <span className="text-xs font-medium text-orange-400 bg-orange-950/15 border border-orange-500/10 px-3 py-2 rounded block leading-relaxed">
                {actionError}
              </span>
            )}

            {/* BOTONES LÓGICOS DE TRANSICIONES DE ESTADO */}
            <div className="space-y-3 pt-2">
              
              {/* Caso 1: Estado = Abierto */}
              {ticket.status === 'Abierto' && (
                <button
                  onClick={handleAutoAssign}
                  disabled={submittingStatus}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 uppercase disabled:opacity-40"
                >
                  <Play className="h-4 w-4" />
                  <span>Asignar Automáticamente</span>
                </button>
              )}

              {/* Caso 2: Estado = Asignado */}
              {ticket.status === 'Asignado' && (
                <button
                  onClick={() => handleStatusTransition('En Proceso')}
                  disabled={submittingStatus}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 uppercase disabled:opacity-40"
                >
                  <Play className="h-4 w-4" />
                  <span>Iniciar Atención</span>
                </button>
              )}

              {/* Caso 3: Estado = En Proceso */}
              {ticket.status === 'En Proceso' && !showPauseInput && !showResolveInput && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    onClick={() => setShowPauseInput(true)}
                    disabled={submittingStatus}
                    className="flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold tracking-wider rounded transition duration-200 uppercase disabled:opacity-40"
                  >
                    <Pause className="h-4 w-4" />
                    <span>Pausar</span>
                  </button>
                  <button
                    onClick={() => setShowResolveInput(true)}
                    disabled={submittingStatus}
                    className="flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold tracking-wider rounded transition duration-200 uppercase disabled:opacity-40"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Resolver</span>
                  </button>
                </div>
              )}

              {/* Insumo para justificar Pausa (En Espera) */}
              {showPauseInput && (
                <div className="space-y-3 p-3 bg-purple-950/10 border border-purple-500/10 rounded">
                  <label className="block text-[10px] text-purple-400 font-bold uppercase tracking-wider">Justificación de la Pausa</label>
                  <textarea
                    rows={3}
                    required
                    value={justificacionPausa}
                    onChange={(e) => setJustificacionPausa(e.target.value)}
                    placeholder="Escriba el motivo técnico por el cual detiene el SLA..."
                    className="w-full px-3 py-2 bg-transparent text-white placeholder-white/20 border border-white/10 rounded focus:outline-none focus:border-purple-500 text-xs resize-none"
                  />
                  <div className="flex gap-2 justify-end">
                    <button 
                      onClick={() => setShowPauseInput(false)}
                      className="px-3 py-1.5 text-[10px] text-white/50 hover:text-white font-semibold uppercase"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={() => handleStatusTransition('En Espera', { justificacion_pausa: justificacionPausa })}
                      disabled={submittingStatus || !justificacionPausa.trim()}
                      className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-[10px] font-bold rounded uppercase tracking-wider disabled:opacity-40"
                    >
                      Confirmar Pausa
                    </button>
                  </div>
                </div>
              )}

              {/* Entrada para agregar comentario de solución (Resuelto) */}
              {showResolveInput && (
                <div className="space-y-3 p-3 bg-emerald-950/10 border border-emerald-500/10 rounded">
                  <label className="block text-[10px] text-emerald-400 font-bold uppercase tracking-wider">Comentario de Solución</label>
                  <textarea
                    rows={3}
                    required
                    value={comentarioSolucion}
                    onChange={(e) => setComentarioSolucion(e.target.value)}
                    placeholder="Describa brevemente la solución del problema..."
                    className="w-full px-3 py-2 bg-transparent text-white placeholder-white/20 border border-white/10 rounded focus:outline-none focus:border-emerald-500 text-xs resize-none"
                  />
                  <div className="flex gap-2 justify-end">
                    <button 
                      onClick={() => setShowResolveInput(false)}
                      className="px-3 py-1.5 text-[10px] text-white/50 hover:text-white font-semibold uppercase"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={() => handleStatusTransition('Resuelto', { comentario_solucion: comentarioSolucion })}
                      disabled={submittingStatus || !comentarioSolucion.trim()}
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold rounded uppercase tracking-wider disabled:opacity-40"
                    >
                      Confirmar Solución
                    </button>
                  </div>
                </div>
              )}

              {/* Caso 4: Estado = En Espera */}
              {ticket.status === 'En Espera' && (
                <button
                  onClick={() => handleStatusTransition('En Proceso')}
                  disabled={submittingStatus}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 uppercase disabled:opacity-40"
                >
                  <Play className="h-4 w-4" />
                  <span>Reanudar Atención</span>
                </button>
              )}

              {/* Caso 5: Estado = Resuelto */}
              {ticket.status === 'Resuelto' && (
                <button
                  onClick={() => handleStatusTransition('Cerrado')}
                  disabled={submittingStatus}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold tracking-wider rounded transition duration-200 uppercase disabled:opacity-40"
                >
                  <Lock className="h-4 w-4" />
                  <span>Confirmar Cierre de Ticket</span>
                </button>
              )}

              {/* Caso del Estado Final: Cerrado */}
              {ticket.status === 'Cerrado' && (
                <div className="flex items-center gap-2 p-3 bg-white/5 border border-white/5 rounded text-white/40 text-xs font-semibold justify-center">
                  <Lock className="h-4 w-4" />
                  <span>Ticket Cerrado de Forma Permanente</span>
                </div>
              )}

            </div>
          </div>

          {/* Tarjeta de seguimiento de SLA y detalles de metadatos */}
          <div className="bg-[#22262B]/20 border border-white/5 rounded-md p-6 space-y-4">
            <h3 className="text-xs font-bold text-white/40 uppercase tracking-wider">Historial Técnico</h3>
            
            <div className="space-y-3 text-xs">
              <div className="flex justify-between">
                <span className="text-white/40">Versión Concurrencia (OCC)</span>
                <span className="font-semibold text-white/80 font-mono">v{ticket.__v}</span>
              </div>
              
              <div className="flex justify-between">
                <span className="text-white/40">Tiempo Pausado Acumulado</span>
                <span className="font-semibold text-white/80 font-mono">
                  {ticket.minutos_en_espera_acumulados ? `${ticket.minutos_en_espera_acumulados.toFixed(2)} min` : '0.00 min'}
                </span>
              </div>
              
              {/* Representar condicionalmente los metadatos de la solución */}
              {ticket.comentario_solucion && (
                <div className="pt-3 border-t border-white/5 space-y-1">
                  <span className="block text-[10px] text-emerald-400 font-bold uppercase tracking-wider">Detalles de la Solución</span>
                  <p className="text-white/70 leading-relaxed break-words">{ticket.comentario_solucion}</p>
                </div>
              )}

              {/* Representar condicionalmente metadatos de Pausa */}
              {ticket.justificacion_pausa && (
                <div className="pt-3 border-t border-white/5 space-y-1">
                  <span className="block text-[10px] text-purple-400 font-bold uppercase tracking-wider">Última Pausa Registrada</span>
                  <p className="text-white/70 leading-relaxed break-words">{ticket.justificacion_pausa}</p>
                </div>
              )}
            </div>
          </div>

        </div>

      </div>

    </div>
  );
};

export default TicketDetail;