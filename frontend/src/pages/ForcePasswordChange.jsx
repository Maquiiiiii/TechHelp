import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';
import { useAuthStore } from '../store/authStore';
import { KeyRound, CheckCircle2, ShieldAlert, Check, X } from 'lucide-react';

const ForcePasswordChange = () => {
  const navigate = useNavigate();
  const { role, logout, setRequiresPasswordChange } = useAuthStore();
  
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [success, setSuccess] = useState(false);
  const [version, setVersion] = useState(0);

  // Referencia de paralaje para las auroras de malla líquida transformadora
  const blobsContainerRef = useRef(null);

  // Obtener la versión del técnico (OCC) en el soporte
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await api.get('/technicians/me');
        // Recuperar la versión de __v o v
        const currentVersion = res.data.__v !== undefined ? res.data.__v : (res.data.v !== undefined ? res.data.v : 0);
        setVersion(currentVersion);
      } catch (err) {
        console.error('Error al obtener versión del perfil:', err);
      }
    };
    fetchProfile();
  }, []);

  // Bucle de física de paralaje para las auroras de malla líquida transformadora (que coincide con Login.jsx)
  useEffect(() => {
    const target = { x: 0, y: 0 };
    const current = { x: 0, y: 0 };

    const handleMouseMove = (e) => {
      const xCenter = window.innerWidth / 2;
      const yCenter = window.innerHeight / 2;
      target.x = -((e.clientX - xCenter) / xCenter) * 60;
      target.y = -((e.clientY - yCenter) / yCenter) * 60;
    };

    window.addEventListener('mousemove', handleMouseMove);

    let frameId;
    const animate = () => {
      current.x += (target.x - current.x) * 0.05;
      current.y += (target.y - current.y) * 0.05;

      if (blobsContainerRef.current) {
        blobsContainerRef.current.style.transform = `translate3d(${current.x}px, ${current.y}px, 0)`;
      }

      frameId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      cancelAnimationFrame(frameId);
    };
  }, []);

  // Reglas de validación activas
  const hasMinLength = newPassword.length >= 8;
  const isNotDefault = !['tech123', 'client123', 'admin123', 'password123'].includes(newPassword.toLowerCase());
  const doPasswordsMatch = newPassword === confirmPassword && confirmPassword !== '';
  const isFormValid = hasMinLength && isNotDefault && doPasswordsMatch;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');

    if (!isFormValid) {
      setErrorMsg('Por favor, asegúrese de cumplir con todos los criterios de seguridad.');
      return;
    }

    setLoading(true);
    try {
      await api.put('/technicians/update-initial-password', {
        password: newPassword,
        version: version
      });
      
      setSuccess(true);
      
      // Actualizar el estado de Zustand y LocalStorage
      setRequiresPasswordChange(false);
      
      setTimeout(() => {
        if (role === 'Tecnico') {
          navigate('/tickets/all');
        } else {
          navigate('/');
        }
      }, 2000);
    } catch (err) {
      console.error('Error al actualizar contraseña:', err);
      const msg = err.response?.data?.detail || 'Error al cambiar la contraseña. Intente nuevamente.';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex h-screen w-screen items-center justify-center bg-[#1A1D20] text-[#FFFFFF] overflow-hidden font-sans select-none">
      
      {/* Aurora de malla líquida de fondo: paralaje, transformación, respiración y cambio de color */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0 bg-[#1A1D20]">
        <div 
          ref={blobsContainerRef} 
          className="absolute inset-0 flex items-center justify-center w-full h-full mix-blend-screen"
        >
          <div className="absolute animate-breath-hue-1 -translate-x-[20%] -translate-y-[15%] will-change-[transform,filter,opacity]">
            <div className="w-[600px] h-[600px] bg-[#0066FF] animate-blob-1 will-change-[transform,border-radius]" />
          </div>
          
          <div className="absolute animate-breath-hue-2 translate-x-[25%] translate-y-[20%] will-change-[transform,filter,opacity]">
            <div className="w-[500px] h-[500px] bg-[#00D2FF] animate-blob-2 will-change-[transform,border-radius]" />
          </div>
          
          <div className="absolute animate-breath-hue-3 translate-x-[-5%] translate-y-[25%] will-change-[transform,filter,opacity]">
            <div className="w-[450px] h-[450px] bg-[#06b6d4] animate-blob-3 will-change-[transform,border-radius]" />
          </div>
        </div>
      </div>

      {/* Contenedor principal sin tarjeta */}
      <div className="relative z-10 flex flex-col items-center justify-center w-full max-w-sm px-6">
        
        {/* Candado mínimo centrado/icono de llave */}
        <div className="mb-6">
          <div className="p-3 bg-white/5 border border-white/10 rounded-full">
            <KeyRound className="h-10 w-10 text-[#00D2FF] animate-pulse" />
          </div>
        </div>

        {/* Encabezados de título */}
        <div className="mb-6 text-center">
          <h2 className="text-xl font-bold tracking-widest text-[#FFFFFF]">CAMBIO OBLIGATORIO</h2>
          <p className="mt-1 text-[10px] tracking-wider uppercase text-white/40">
            Establezca su contraseña corporativa definitiva
          </p>
        </div>

        {/* Mensajes de estado */}
        {errorMsg && (
          <div className="w-full mb-4">
            <span className="block px-3 py-2 text-xs font-medium leading-relaxed tracking-wide border rounded text-orange-500/90 bg-orange-950/10 border-orange-500/10 text-center">
              {errorMsg}
            </span>
          </div>
        )}

        {success ? (
          <div className="w-full py-6 flex flex-col items-center justify-center gap-3 text-center bg-transparent">
            <CheckCircle2 className="h-12 w-12 text-[#00D2FF] animate-bounce" />
            <span className="text-sm font-bold text-white uppercase tracking-widest">¡Contraseña cambiada con éxito!</span>
            <span className="text-xs text-white/40">Redirigiendo a su espacio de trabajo...</span>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="w-full space-y-5">
            
            {/* Nueva entrada de contraseña */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                <svg className="w-5 h-5 text-white/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <input
                type="password"
                required
                disabled={loading}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Nueva contraseña"
                className="w-full pl-10 pr-4 py-3 bg-transparent text-[#FFFFFF] placeholder-white/30 border border-[#FFFFFF]/20 rounded-md focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-300 text-sm"
              />
            </div>

            {/* Confirmar entrada de contraseña */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                <svg className="w-5 h-5 text-white/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <input
                type="password"
                required
                disabled={loading}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirmar contraseña"
                className="w-full pl-10 pr-4 py-3 bg-transparent text-[#FFFFFF] placeholder-white/30 border border-[#FFFFFF]/20 rounded-md focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-300 text-sm"
              />
            </div>

            {/* Indicadores de validación calientes */}
            <div className="p-3 border border-white/5 bg-white/5 rounded-md space-y-2 text-xs">
              <div className="flex items-center gap-2">
                {hasMinLength ? (
                  <Check className="h-4 w-4 text-emerald-400" />
                ) : (
                  <X className="h-4 w-4 text-red-400" />
                )}
                <span className={hasMinLength ? 'text-emerald-400' : 'text-white/40'}>
                  Mínimo 8 caracteres
                </span>
              </div>
              <div className="flex items-center gap-2">
                {isNotDefault ? (
                  <Check className="h-4 w-4 text-emerald-400" />
                ) : (
                  <X className="h-4 w-4 text-red-400" />
                )}
                <span className={isNotDefault ? 'text-emerald-400' : 'text-white/40'}>
                  No es una clave por defecto
                </span>
              </div>
              <div className="flex items-center gap-2">
                {doPasswordsMatch ? (
                  <Check className="h-4 w-4 text-emerald-400" />
                ) : (
                  <X className="h-4 w-4 text-red-400" />
                )}
                <span className={doPasswordsMatch ? 'text-emerald-400' : 'text-white/40'}>
                  Las contraseñas coinciden
                </span>
              </div>
            </div>

            {/* Acciones de formulario */}
            <div className="space-y-3">
              <button
                type="submit"
                disabled={loading || !isFormValid}
                className="w-full py-3 bg-[#0066FF] text-[#FFFFFF] font-bold text-sm tracking-widest rounded-md hover:bg-[#00D2FF] transition duration-300 uppercase shadow-[0_0_15px_rgba(0,102,255,0.2)] hover:shadow-[0_0_20px_rgba(0,210,255,0.4)] disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {loading ? 'Guardando...' : 'GUARDAR CONTRASEÑA'}
              </button>

              <button
                type="button"
                disabled={loading}
                onClick={() => {
                  logout();
                  navigate('/login');
                }}
                className="w-full py-2 text-center text-xs text-white/30 hover:text-[#FFFFFF] transition duration-300 uppercase font-semibold"
              >
                Cancelar y Salir
              </button>
            </div>

          </form>
        )}

      </div>
    </div>
  );
};

export default ForcePasswordChange;