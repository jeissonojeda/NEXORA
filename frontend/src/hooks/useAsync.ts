import { useCallback, useEffect, useRef, useState } from 'react';

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface AxiosLikeError {
  isAxiosError?: boolean;
  code?: string;
  message?: string;
  response?: {
    status?: number;
    data?: unknown;
  };
}

function isAxiosLike(err: unknown): err is AxiosLikeError {
  return (
    typeof err === 'object' &&
    err !== null &&
    ('isAxiosError' in err || 'response' in err)
  );
}

function detailFromValidationArray(detail: unknown[]): string | null {
  const parts: string[] = [];
  for (const item of detail) {
    if (typeof item === 'string') {
      parts.push(item);
      continue;
    }
    if (item && typeof item === 'object' && 'msg' in item) {
      const record = item as Record<string, unknown>;
      const loc = Array.isArray(record.loc) ? (record.loc as unknown[]) : [];
      const field = loc
        .filter((segment) => segment !== 'body')
        .join('.');
      const msg = String(record.msg);
      parts.push(field ? `${field}: ${msg}` : msg);
    }
  }
  return parts.length > 0 ? parts.join(' | ') : null;
}

/**
 * Traduce un error de Axios a un mensaje comprensible para el usuario,
 * diferenciando conectividad, autenticación, permisos y errores HTTP.
 * El detalle técnico completo queda en el objeto original (logs).
 */
export function extractErrorMessage(err: unknown): string {
  if (isAxiosLike(err)) {
    const status = err.response?.status;
    const data = err.response?.data as
      | { detail?: unknown; error_code?: string }
      | undefined;
    const detail = data?.detail;

    if (err.response === undefined) {
      if (err.code === 'ECONNABORTED' || /timeout/i.test(err.message ?? '')) {
        return (
          'La solicitud tardó demasiado en responder. Verifique la conexión ' +
          'con el servidor e intente de nuevo.'
        );
      }
      return (
        'No se pudo conectar con el servidor. Verifique que el backend esté ' +
        'en ejecución y que exista conexión de red.'
      );
    }

    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail)) {
      const message = detailFromValidationArray(detail);
      if (message) return `Datos inválidos: ${message}`;
    }
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const nested = (detail as Record<string, unknown>).message;
      if (typeof nested === 'string' && nested.trim()) return nested;
    }

    switch (status) {
      case 400:
        return (
          'La solicitud no es válida o está incompleta. Verifique el archivo ' +
          'e intente de nuevo.'
        );
      case 401:
        return 'La sesión expiró o no es válida. Inicie sesión nuevamente.';
      case 403:
        return 'No tiene permiso para realizar esta acción.';
      case 404:
        return (
          'No se encontró el recurso solicitado. Verifique que el backend ' +
          'esté actualizado.'
        );
      case 409:
        return 'La operación entra en conflicto con el estado actual del sistema.';
      case 413:
        return 'El archivo o la solicitud superan el tamaño permitido.';
      case 422:
        return (
          'Los datos enviados no cumplen las validaciones requeridas. ' +
          'Revise el archivo y vuelva a intentarlo.'
        );
      case 500:
        return (
          'El servidor encontró un error al procesar el archivo. Contacte al ' +
          'administrador e indique el momento exacto del fallo.'
        );
      case 502:
      case 503:
      case 504:
        return 'El servidor no está disponible en este momento. Intente de nuevo.';
      default:
        return `El servidor respondió con un error inesperado (HTTP ${status ?? '??'}).`;
    }
  }
  if (err instanceof Error) {
    const message = err.message;
    // Evita mostrar mensajes técnicos crudos al usuario.
    if (/network error|request failed|axioserror/i.test(message)) {
      return (
        'No se pudo completar la solicitud. Verifique que el backend esté en ' +
        'ejecución y que exista conexión de red.'
      );
    }
    return message || 'Error inesperado';
  }
  return 'Error inesperado';
}

/** Extrae el `error_code` del backend cuando existe (para lógica/UI). */
export function extractErrorCode(err: unknown): string | null {
  if (isAxiosLike(err)) {
    const data = err.response?.data as { error_code?: unknown } | undefined;
    if (typeof data?.error_code === 'string') return data.error_code;
  }
  return null;
}

export function useAsync<T>(
  asyncFn: () => Promise<T>,
  deps: unknown[] = [],
) {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: true,
    error: null,
  });
  const fnRef = useRef(asyncFn);
  fnRef.current = asyncFn;

  const execute = useCallback(async () => {
    setState({ data: null, loading: true, error: null });
    try {
      const data = await fnRef.current();
      setState({ data, loading: false, error: null });
      return data;
    } catch (err) {
      setState({ data: null, loading: false, error: extractErrorMessage(err) });
      return null;
    }
  }, []);

  useEffect(() => {
    void execute();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { ...state, reload: execute };
}
