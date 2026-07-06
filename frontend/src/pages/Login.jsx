import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../utils/api';
import { useAuthStore } from '../store/authStore';

const Login = () => {
  const navigate = useNavigate();
  const setLoginSuccess = useAuthStore((state) => state.setLoginSuccess);

  // Referencia al contenedor real que contiene las gotas de malla Aurora.
  const blobsContainerRef = useRef(null);

  // Estados del formulario
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

  // Estado del paso de autenticación: 1 = Credenciales, 2 = TOTP MFA
  const [step, setStep] = useState(1);
  const [tempToken, setTempToken] = useState('');

  // Bucle de física de paralaje para las auroras de malla líquida cambiante
  useEffect(() => {
    // Vector de desplazamiento de destino (se desplaza en la dirección opuesta al cursor)
    const target = { x: 0, y: 0 };
    // Coordenadas de desplazamiento interpoladas actuales
    const current = { x: 0, y: 0 };

    const handleMouseMove = (e) => {
      const xCenter = window.innerWidth / 2;
      const yCenter = window.innerHeight / 2;
      
      // Cálculos de paralaje inverso (distancia máxima de desplazamiento = 60 px)
      target.x = -((e.clientX - xCenter) / xCenter) * 60;
      target.y = -((e.clientY - yCenter) / yCenter) * 60;
    };

    window.addEventListener('mousemove', handleMouseMove);

    let frameId;
    const animate = () => {
      // Transición de interpolación lineal suave (LERP)
      current.x += (target.x - current.x) * 0.05;
      current.y += (target.y - current.y) * 0.05;

      // Aplique la transformación directamente para evitar desencadenantes de renderizado del estado de React
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

  // Ayudante para decodificar la carga útil de JWT sin bibliotecas externas
  const decodeJwtPayload = (token) => {
    try {
      const payloadPart = token.split('.')[1];
      const decoded = atob(payloadPart);
      return JSON.parse(decoded);
    } catch (e) {
      console.error('Error decodificando payload JWT:', e);
      return {};
    }
  };

  // Paso 1: enviar credenciales
  const handleStep1Submit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      const response = await api.post('/login/step1', { identifier: email, password });
      
      if (response.data.mfa_required) {
        setTempToken(response.data.temp_token);
        setStep(2);
      } else {
        // Autenticación directa (si se omite o deshabilita mfa para otras funciones)
        const token = response.data.access_token;
        const claims = decodeJwtPayload(token);
        setLoginSuccess(token, claims.role || 'Cliente', claims.sub || email);
        
        if (response.data.requires_password_change) {
          navigate('/change-password');
        } else {
          // Redirección basada en rol (RBAC)
          if (claims.role === 'Tecnico') {
            navigate('/tickets/all');
          } else if (claims.role === 'Cliente') {
            navigate('/tickets');
          } else {
            navigate('/');
          }
        }
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Credenciales inválidas o error de conexión.';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  // Paso 2: envía el código TOTP OTP
  const handleStep2Submit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    try {
      const response = await api.post('/login/step2', {
        temp_token: tempToken,
        code: otpCode
      });
      
      const token = response.data.access_token;
      const claims = decodeJwtPayload(token);
      setLoginSuccess(token, claims.role || 'Administrador', claims.sub || email);
      
      const requiresChange = response.data.requires_password_change || claims.requires_password_change || false;
      
      console.info('MFA validado correctamente. Redirigiendo...');
      if (claims.role === 'Tecnico') {
        if (requiresChange) {
          navigate('/force-password-change');
        } else {
          navigate('/tickets/all');
        }
      } else if (claims.role === 'Cliente') {
        navigate('/tickets');
      } else {
        navigate('/');
      }

    } catch (err) {
      const msg = err.response?.data?.detail || 'Código OTP inválido o expirado.';
      setErrorMsg(msg);
      // Si el bloqueo se activa por 3 fallas, restablezca la entrada otp
      setOtpCode('');
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
          {/* Orbe 1: Azul Tecnológico (La respiración y el tono cambian en el padre, se transforman en el niño) */}
          <div className="absolute animate-breath-hue-1 -translate-x-[20%] -translate-y-[15%] will-change-[transform,filter,opacity]">
            <div className="w-[600px] h-[600px] bg-[#0066FF] animate-blob-1 will-change-[transform,border-radius]" />
          </div>
          
          {/* Orbe 2: Azul Brillante */}
          <div className="absolute animate-breath-hue-2 translate-x-[25%] translate-y-[20%] will-change-[transform,filter,opacity]">
            <div className="w-[500px] h-[500px] bg-[#00D2FF] animate-blob-2 will-change-[transform,border-radius]" />
          </div>
          
          {/* Orbe 3: Tono cian/intermedio */}
          <div className="absolute animate-breath-hue-3 translate-x-[-5%] translate-y-[25%] will-change-[transform,filter,opacity]">
            <div className="w-[450px] h-[450px] bg-[#06b6d4] animate-blob-3 will-change-[transform,border-radius]" />
          </div>
        </div>
      </div>

      {/* Contenedor principal de formularios sin tarjeta */}
      <div className="relative z-10 flex flex-col items-center justify-center w-full max-w-sm px-6">
        
        {/* Icono de candado mínimo centrado */}
        <div className="mb-8">
          <svg className="h-12 w-12 text-[#FFFFFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>

        {/* Encabezados de título */}
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-bold tracking-widest text-[#FFFFFF]">TECHHELP</h2>
          <p className="mt-1 text-xs tracking-wider uppercase text-white/40">
            {step === 1 ? 'Soporte robusto que escala con tu éxito' : 'Verificación de Seguridad (MFA)'}
          </p>
        </div>

        {/* PASO 1: FORMULARIO DE CREDENCIALES */}
        {step === 1 && (
          <form onSubmit={handleStep1Submit} className="w-full space-y-5">
            {/* Entrada de correo electrónico */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                <svg className="w-5 h-5 text-white/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                </svg>
              </div>
              <input
                type="email"
                required
                disabled={loading}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="correo@empresa.cl"
                className="w-full pl-10 pr-4 py-3 bg-transparent text-[#FFFFFF] placeholder-white/30 border border-[#FFFFFF]/20 rounded-md focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-300 text-sm"
              />
            </div>

            {/* Entrada de contraseña */}
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
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-10 pr-4 py-3 bg-transparent text-[#FFFFFF] placeholder-white/30 border border-[#FFFFFF]/20 rounded-md focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-300 text-sm"
              />
            </div>

            {/* Botón Enviar */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-[#0066FF] text-[#FFFFFF] font-bold text-sm tracking-widest rounded-md hover:bg-[#00D2FF] transition duration-300 uppercase shadow-[0_0_15px_rgba(0,102,255,0.2)] hover:shadow-[0_0_20px_rgba(0,210,255,0.4)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Validando...' : 'INICIAR SESIÓN'}
            </button>
          </form>
        )}

        {/* PASO 2: FORMULARIO TOTP DE MFA */}
        {step === 2 && (
          <form onSubmit={handleStep2Submit} className="w-full space-y-5">
            <p className="mb-2 text-xs leading-relaxed text-center text-white/40">
              Ingrese el código de seguridad de 6 dígitos de su aplicación autenticadora.
            </p>
            
            {/* Entrada OTP de 6 dígitos */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                <svg className="w-5 h-5 text-white/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <input
                type="text"
                required
                maxLength={6}
                disabled={loading}
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                className="w-full pl-10 pr-4 py-3 bg-transparent text-[#FFFFFF] placeholder-white/30 border border-[#FFFFFF]/20 rounded-md tracking-[0.5em] text-center focus:outline-none focus:ring-0 focus:border-[#00D2FF] transition duration-300 text-sm font-semibold"
              />
            </div>

            {/* Botón Enviar */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-[#0066FF] text-[#FFFFFF] font-bold text-sm tracking-widest rounded-md hover:bg-[#00D2FF] transition duration-300 uppercase shadow-[0_0_15px_rgba(0,102,255,0.2)] hover:shadow-[0_0_20px_rgba(0,210,255,0.4)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Verificando...' : 'VERIFICAR CÓDIGO'}
            </button>

            {/* Botón Volver al paso 1 */}
            <button
              type="button"
              disabled={loading}
              onClick={() => {
                setStep(1);
                setOtpCode('');
                setErrorMsg('');
              }}
              className="w-full text-center text-xs text-white/30 hover:text-[#FFFFFF] transition duration-300"
            >
              Volver
            </button>
          </form>
        )}

        {/* Contenedor de mensaje de error */}
        {errorMsg && (
          <div className="w-full mt-4 text-center">
            <span className="block px-3 py-2 text-xs font-medium leading-relaxed tracking-wide border rounded text-orange-500/90 bg-orange-950/10 border-orange-500/10">
              {errorMsg}
            </span>
          </div>
        )}

        {step === 1 && (
          <a
            href="#forgot"
            className="mt-6 text-xs text-white/40 hover:text-[#FFFFFF] transition duration-300 font-medium tracking-wide"
          >
            ¿Olvidó su contraseña?
          </a>
        )}

      </div>
    </div>
  );
};

export default Login;