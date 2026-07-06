import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../utils/api';
import { Star, ShieldAlert, CheckCircle2 } from 'lucide-react';

const Survey = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [loading, setLoading] = useState(true);
  const [isInvalid, setIsInvalid] = useState(false);
  const [rating, setRating] = useState(0);
  const [comments, setComments] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

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
        console.error('Validation error:', err);
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
      setErrorMsg('Por favor seleccione una valoración de 1 a 5 estrellas.');
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
      console.error('Error submitting survey:', err);
      const msg = err.response?.data?.detail || 'Error al enviar la encuesta.';
      setErrorMsg(msg);
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
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#00D2FF]/20 border-t-[#00D2FF]"></div>
      </div>
    );
  }

  // Interceptar tokens vencidos o ya usados
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
      <div className="w-full max-w-lg bg-[#22262B] border border-white/10 rounded-md p-8 space-y-6 shadow-2xl">
        <div className="text-center space-y-2 border-b border-white/5 pb-4">
          <h1 className="text-xl font-bold tracking-widest text-[#00D2FF]">TECHHELP</h1>
          <h2 className="text-sm font-bold tracking-wider text-white uppercase">Encuesta de Satisfacción</h2>
        </div>

        {errorMsg && (
          <div className="p-3 bg-red-950/10 border border-red-500/10 rounded text-center text-xs text-red-400">
            {errorMsg}
          </div>
        )}

        {success ? (
          <div className="p-6 bg-emerald-950/15 border border-emerald-500/10 rounded text-center space-y-3">
            <CheckCircle2 className="h-10 w-10 text-emerald-400 mx-auto" />
            <h3 className="text-sm font-bold uppercase text-white">¡Muchas Gracias!</h3>
            <p className="text-xs text-white/60">Su valoración ha sido registrada con éxito.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="flex justify-center gap-2">
              {[1, 2, 3, 4, 5].map((stars) => (
                <button
                  key={stars}
                  type="button"
                  onClick={() => setRating(stars)}
                  className="p-1 hover:scale-110 transition duration-150"
                >
                  <Star className={`h-8 w-8 ${stars <= rating ? 'text-yellow-400 fill-yellow-400' : 'text-white/20'}`} />
                </button>
              ))}
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-bold text-white/55 uppercase tracking-wider">
                Comentarios adicionales (opcional)
              </label>
              <textarea
                rows={4}
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                className="w-full px-4 py-3 bg-transparent text-white border border-white/10 rounded focus:outline-none focus:border-[#00D2FF] text-xs resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={submitting || rating === 0}
              className="w-full py-3 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded transition duration-200 uppercase"
            >
              Enviar Calificación
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default Survey;