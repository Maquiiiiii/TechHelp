import React from 'react';
import { ShieldAlert, RotateCw } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary ha capturado un error crítico:", error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    try {
      localStorage.clear();
      window.location.href = '/login';
    } catch (e) {
      console.error(e);
      window.location.href = '/';
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen w-screen bg-[#1A1D20] text-white flex items-center justify-center p-6 font-sans">
          <div className="max-w-md w-full bg-[#22262B] border border-red-500/20 p-8 rounded-lg shadow-2xl space-y-6 text-center animate-fade-in">
            <div className="flex justify-center">
              <ShieldAlert className="text-red-500 h-16 w-16 animate-pulse" />
            </div>
            <div className="space-y-2">
              <h1 className="text-lg font-bold tracking-wider uppercase text-white">Fallo de Renderizado</h1>
              <p className="text-xs text-white/50 leading-relaxed">
                Se ha producido un error inesperado al inicializar o actualizar la interfaz del sistema.
              </p>
            </div>
            {this.state.error && (
              <div className="p-3 bg-red-950/10 border border-red-500/10 rounded text-[11px] font-mono text-red-400 text-left max-h-32 overflow-y-auto break-all">
                {this.state.error.toString()}
              </div>
            )}
            <div className="pt-2 flex flex-col gap-2">
              <button
                onClick={() => window.location.reload()}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-[#0066FF] hover:bg-[#00D2FF] text-white text-xs font-bold tracking-wider rounded uppercase transition duration-200"
              >
                <RotateCw className="h-4 w-4" />
                <span>Reintentar Carga</span>
              </button>
              <button
                onClick={this.handleReset}
                className="w-full px-4 py-2 border border-white/10 hover:border-white/20 text-white/60 hover:text-white text-xs font-bold tracking-wider rounded uppercase transition duration-200"
              >
                Limpiar Caché y Sesión
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;