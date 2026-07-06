import { useEffect, useRef } from 'react';

/**
 * Hook de React para autoguardar borradores en LocalStorage cada 30 segundos.
 * @param {string} key Clave única en LocalStorage
 * @param {cualquier} valor Valor a guardar (borrador)
 * @param {función} onLoad Callback opcional al cargar el borrador recuperado
 */
export const useAutoSave = (key, value, onLoad) => {
  const valueRef = useRef(value);

  // Mantenga el valor actualizado dentro de la referencia sin volver a activar el intervalo
  useEffect(() => {
    valueRef.current = value;
  }, [value]);

  // Recuperar borrador inicial en el montaje
  useEffect(() => {
    const saved = localStorage.getItem(key);
    if (saved && onLoad) {
      try {
        onLoad(JSON.parse(saved));
      } catch (e) {
        onLoad(saved);
      }
    }
  }, [key]);

  // Configurar un intervalo de guardado automático de 30 segundos
  useEffect(() => {
    const interval = setInterval(() => {
      if (valueRef.current) {
        localStorage.setItem(key, typeof valueRef.current === 'object' ? JSON.stringify(valueRef.current) : valueRef.current);
      }
    }, 30 * 1000); // 30 segundos exactos

    return () => clearInterval(interval);
  }, [key]);

  // Función auxiliar para borrar el borrador tras un envío exitoso
  const clearDraft = () => {
    localStorage.removeItem(key);
  };

  return { clearDraft };
};

export default useAutoSave;