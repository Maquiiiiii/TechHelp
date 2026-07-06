import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../utils/api';
import { Star, ShieldAlert, CheckCircle2, MessageSquare } from 'lucide-react';

const FeedbackSurvey = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  // Estados de la pagina
  const [loading, setLoading] = useState(true);
  const [isInvalid, setIsInvalid] = useState(false);
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [comments, setComments] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Validar token en el montaje
  useEffect(() => {
    const validateToken = async () => {
      if (!token) {
        setIsInvalid(true);
        setLoading(false);
        return;
      }

      try {
        await api.get(`/feedback/validate?token=${token}`);
        setIsInvalid(false);
      } catch (err) {
        console.error('Token validation failed:', err);
        setIsInvalid(true);
      } finally {
        setLoading(false);
      }
    };

    validateToken();
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (rating < 1 || rating > 5) {
      setErrorMsg('Por favor seleccione una calificación del 1 al 5.');
      return;
    }

    setSubmitting(true);
    setErrorMsg('');

    try {
      await api.post('/feedback', {
        token,
        valoracion: rating,
        comentarios: comments || null
      });
      setSuccess(true);
    } catch (err) {
      console.error('Error submitting feedback:', err);
      const msg = err.response?.data?.detail || 'Error al enviar la encuesta. Intente nuevamente.';
      setErrorMsg(msg);
      // Si el servidor devuelve un error debido a que ya se nos o caducó, establezca no válido
      if (err.response?.status === 400 || err.response?.status === 403) {
        setIsInvalid(true);
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#1A1D20] text-white">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
          <span className="text-sm text-white/40 tracking-wider">Cargando encuesta...</span>
        </div>
      </div>
    );
  }

  // Requisito de Bloque Obligatorio (Representar exclusivamente: "Esta encuesta ya fue respondida")
  if (isInvalid) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#1A1D20] p-4 text-white">
        <div className="w-full max-w-md bg-[#22262B] border border-white/10 rounded-md p-8 space-y-4 shadow-2xl text-center">
          <div className="flex justify-center">
            <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-full">
              <ShieldAlert className="h-7 w-7" />
            </div>
          </div>
          <h2 className="text-lg font-bold text-white uppercase tracking-wider">Acceso Restringido</h2>
          <p className="text-sm text-red-400 font-semibold leading-relaxed">
            Esta encuesta ya fue respondida
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#1A1D20] p-4 text-white font-sans">
      
      {/* Fondo Estilo de malla líquida */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute inset-0 w-full h-full flex items-center justify-center mix-blend-screen opacity-20">
          <div className="absolute translate-x-[15%] w-[450px] h-[450px] bg-[#0066FF] blur-[100px] rounded-full" />
          <div className="absolute -translate-x-[15%] w-[450px] h-[450px] bg-[#00D2FF] blur-[100px] rounded-full" />
        </div>
      </div>

      <div className="w-full max-w-lg bg-[#22262B] border border-white/10 rounded-md p-8 space-y-6 shadow-2xl relative z-10">
        
        {/* encabezamiento */}
        <div className="text-center space-y-2 border-b border-white/5 pb-4">
          <h1 className="text-xl font-bold tracking-widest text-[#00D2FF]">TECHHELP</h1>
          <h2 className="text-sm font-bold tracking-wider text-white uppercase">Encuesta de Satisfacción</h2>
          <p className="text-xs text-white/40">Su opinión es fundamental para ayudarnos a mejorar el nivel de servicio contratado.</p>
        </div>

        {/* Mensajes de estado */}
        {errorMsg && (
          <div className="p-3 bg-red-950/10 border border-red-500/10 rounded text-center">
            <span className="text-xs font-semibold text-red-400">{errorMsg}</span>
          </div>
        )}

        {success ? (
          <div className="p-6 bg-emerald-950/15 border border-emerald-500/10 rounded flex flex-col items-center justify-center gap-3 text-center">
            <CheckCircle2 className="h-10 w-10 text-emerald-400 animate-bounce" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">¡Muchas Gracias!</h3>
            <p className="text-xs text-white/60 leading-relaxed">
              Su valoración ha sido registrada con éxito. Agradecemos su tiempo para ayudarnos a mantener los estándares de calidad.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            
            {/* Selector de Estrellas de Calificación (Obligatorio, escala 1 a 5) */}
            <div className="space-y-3 text-center">
              <label className="block text-xs font-bold text-white/55 uppercase tracking-wider">
                ¿Cómo calificaría la resolución de su ticket? *
              </label>
              
              <div className="flex items-center justify-center gap-2">
                {[1, 2, 3, 4, 5].map((index) => {
                  const active = index <= (hoverRating || rating);
                  return (
                    <button
                      key={index}
                      type="button"
                      disabled={submitting}
                      onClick={() => setRating(index)}
                      onMouseEnter={() => setHoverRating(index)}
                      onMouseLeave={() => setHoverRating(0)}
                      className="p-1 transition duration-150 transform hover:scale-110 focus:outline-none"
                    >
                      <Star 
                        className={`h-8 w-8 ${
                          active 
                            ? 'text-yellow-400 fill-yellow-400 filter drop-shadow-[0_0_8px_rgba(250,204,21,0.35)]' 
                            : 'text-white/20'
                        }`} 
                      />
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Entrada de comentarios opcionales */}
            <div className="space-y-2">
              <label className="flex items-center gap-1.5 text-xs font-bold text-white/55 uppercase tracking-wider">
                <MessageSquare className="h-4 w-4 text-[#00D2FF]" />
                <span>Comentarios adicionales (opcional)</span>
              </label>
              <textarea
                rows={4}
                disabled={submitting}
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                placeholder="Escriba su experiencia o detalles adicionales sobre la atención recibida..."
                className="w-full px-4 py-3 bg-transparent text-white placeholder-white/20 border border-white/10 rounded focus:outline-none focus:border-[#00D2FF] transition duration-200 text-xs resize-none"
              />
            </div>

            {/* Botón Enviar */}
            <button
              type="submit"
              disabled={submitting || rating === 0}
              className="w-full py-3 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 uppercase disabled:opacity-40 shadow-[0_0_15px_rgba(0,102,255,0.2)]"
            >
              {submitting ? 'Enviando...' : 'Enviar Calificación'}
            </button>

          </form>
        )}

      </div>
    </div>
  );
};

export default FeedbackSurvey;