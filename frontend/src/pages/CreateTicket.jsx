import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';
import { useAuthStore } from '../store/authStore';

const CreateTicket = () => {
  const navigate = useNavigate();
  const { role, organizationRut } = useAuthStore();

  // Estados del formulario
  const [title, setTitle] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [categoria, setCategoria] = useState('');
  const [prioridad, setPrioridad] = useState('');
  const [description, setDescription] = useState('');
  const [attachment, setAttachment] = useState(null);
  const [fileError, setFileError] = useState('');

  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

  // Establecer RUT del cliente automáticamente si el rol del cliente
  useEffect(() => {
    if (role === 'Cliente' && organizationRut) {
      setCustomerId(organizationRut);
    }
  }, [role, organizationRut]);

  // Validar la longitud de la descripción (debe tener >= 20 caracteres)
  const isDescriptionValid = description.trim().length >= 20;

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setFileError('');
    if (!file) {
      setAttachment(null);
      return;
    }
    const allowedExtensions = ['pdf', 'png', 'jpg'];
    const fileExtension = file.name.split('.').pop().toLowerCase();
    
    if (!allowedExtensions.includes(fileExtension)) {
      setFileError('Formato no permitido');
      setAttachment(null);
      e.target.value = '';
      return;
    }
    
    if (file.size > 5 * 1024 * 1024) {
      setFileError('El archivo supera los 5MB');
      setAttachment(null);
      e.target.value = '';
      return;
    }
    
    setAttachment(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setFileError('');

    if (!isDescriptionValid) {
      setErrorMsg('La descripción debe tener al menos 20 caracteres.');
      return;
    }

    setLoading(true);
    try {
      // Paso 1: crear el documento del ticket
      const response = await api.post('/tickets', {
        title,
        customer_id: role === 'Cliente' ? organizationRut : customerId,
        categoria,
        prioridad,
        description
      });
      
      const createdTicket = response.data;
      const ticketId = createdTicket._id || createdTicket.id;

      // Paso 2: Cargue el archivo si lo selecciona, esperando que la creación del ticket sea exitosa
      if (attachment && ticketId) {
        const formData = new FormData();
        formData.append('file', attachment);

        await api.post(`/tickets/${ticketId}/attachments`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      }

      // Redirigir a la página del listado en caso de éxito
      navigate('/tickets');
    } catch (err) {
      console.error('Error creating ticket:', err);
      console.log('Error real del backend (422/400):', err.response?.data?.detail);
      
      let msg = 'No se pudo crear el ticket. Verifique los datos e intente de nuevo.';
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (typeof detail === 'string') {
          msg = detail;
        } else if (Array.isArray(detail)) {
          // Convierta una serie de errores de validación de Pydantic en oraciones legibles
          msg = detail.map(d => {
            const field = d.loc && d.loc.length > 1 ? d.loc.slice(1).join('.') : 'campo';
            return `${field}: ${d.msg}`;
          }).join(' | ');
        } else {
          msg = JSON.stringify(detail);
        }
      }
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      
      {/* encabezamiento */}
      <div>
        <h2 className="text-xl font-bold tracking-wide text-white">Nuevo Ticket de Soporte</h2>
        <p className="text-xs text-white/40 mt-1">
          Complete los campos detallados a continuación para registrar un nuevo incidente de soporte.
        </p>
      </div>

      {/* Formulario limpio sin tarjeta */}
      <form onSubmit={handleSubmit} className="space-y-6 bg-transparent">
        
        {/* Entrada de título */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider">Título del Incidente</label>
          <input
            type="text"
            required
            disabled={loading}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ej: Caída de enlace de datos principal"
            className="w-full px-4 py-3 bg-transparent text-[#FFFFFF] placeholder-white/20 border border-white/10 rounded focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-200 text-sm"
          />
        </div>

        {/* Entrada de identificación de cliente (RUT) */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider">RUT de la Organización</label>
          <input
            type="text"
            required
            disabled={loading || role === 'Cliente'}
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            placeholder="Ej: 12.345.678-9"
            className="w-full px-4 py-3 bg-transparent text-[#FFFFFF] placeholder-white/20 border border-white/10 rounded focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-200 text-sm font-mono disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>

        {/* Cuadrícula de Categorías y Prioridades */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          {/* Seleccionar categoría */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider">Categoría</label>
            <select
              required
              disabled={loading}
              value={categoria}
              onChange={(e) => setCategoria(e.target.value)}
              className="w-full px-4 py-3 bg-[#22262B] text-[#FFFFFF] border border-white/10 rounded focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-200 text-sm"
            >
              <option value="" disabled>Seleccione una categoría</option>
              <option value="Hardware">Hardware</option>
              <option value="Software">Software</option>
              <option value="Redes">Redes</option>
            </select>
          </div>

          {/* Seleccionar prioridad */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider">Prioridad</label>
            <select
              required
              disabled={loading}
              value={prioridad}
              onChange={(e) => setPrioridad(e.target.value)}
              className="w-full px-4 py-3 bg-[#22262B] text-[#FFFFFF] border border-white/10 rounded focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-200 text-sm"
            >
              <option value="" disabled>Seleccione una prioridad</option>
              <option value="Baja">Baja</option>
              <option value="Media">Media</option>
              <option value="Alta">Alta</option>
              <option value="Crítica">Crítica</option>
            </select>
          </div>
        </div>

        {/* Descripción Área de texto */}
        <div className="space-y-1.5">
          <div className="flex justify-between items-center">
            <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider">Descripción Detallada</label>
            <span className={`text-[10px] tracking-wide font-semibold ${isDescriptionValid ? 'text-white/40' : 'text-orange-400'}`}>
              {description.length} caracteres (mínimo 20)
            </span>
          </div>
          <textarea
            required
            rows={5}
            disabled={loading}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describa el comportamiento errático observado, mensajes de error y pasos de reproducción..."
            className="w-full px-4 py-3 bg-transparent text-[#FFFFFF] placeholder-white/20 border border-white/10 rounded focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-200 text-sm resize-none"
          />
        </div>

        {/* Entrada de archivos adjuntos */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider">
            Archivo Adjunto (Opcional - PDF, PNG o JPG hasta 5MB)
          </label>
          <input
            type="file"
            disabled={loading}
            onChange={handleFileChange}
            accept=".pdf,.png,.jpg,.jpeg"
            className="w-full px-4 py-3 bg-transparent text-white/70 placeholder-white/20 border border-white/10 rounded focus:outline-none focus:border-[#00D2FF] text-xs transition duration-200"
          />
          {fileError && (
            <p className="text-xs font-semibold text-orange-400 mt-1">{fileError}</p>
          )}
        </div>

        {/* mensaje de error */}
        {errorMsg && (
          <div className="text-center">
            <span className="text-xs font-medium text-orange-500 bg-orange-950/10 px-3 py-2 border border-orange-500/10 rounded block">
              {errorMsg}
            </span>
          </div>
        )}

        {/* Botones de acciones */}
        <div className="flex items-center justify-end gap-4 pt-2">
          <button
            type="button"
            disabled={loading}
            onClick={() => navigate('/tickets')}
            className="px-5 py-2.5 rounded text-white/60 hover:text-white hover:bg-white/5 transition duration-200 text-xs font-bold uppercase tracking-wider"
          >
            Cancelar
          </button>
          
          <button
            type="submit"
            disabled={loading || !isDescriptionValid || !title || !customerId || !categoria || !prioridad}
            className="px-5 py-2.5 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 shadow-[0_0_15px_rgba(0,102,255,0.2)] hover:shadow-[0_0_20px_rgba(0,210,255,0.4)] disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none"
          >
            {loading ? 'ENVIANDO...' : 'REGISTRAR TICKET'}
          </button>
        </div>

      </form>
    </div>
  );
};

export default CreateTicket;