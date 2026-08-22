import { useEffect, useState } from 'react';
import type { HealthStatus } from '../types';
import api from '../services/api';

interface UseHealthResult {
  health: HealthStatus | null;
  error: string | null;
  loading: boolean;
}

export function useHealth(): UseHealthResult {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchHealth(): Promise<void> {
      try {
        const response = await api.get<HealthStatus>('/health');
        if (!cancelled) {
          setHealth(response.data);
        }
      } catch {
        if (!cancelled) {
          setError('No se pudo conectar con el backend');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void fetchHealth();

    return () => {
      cancelled = true;
    };
  }, []);

  return { health, error, loading };
}
