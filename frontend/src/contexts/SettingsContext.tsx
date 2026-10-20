import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useAuth } from './AuthContext';
import { getSettings } from '../services/settings';
import { configureCurrency } from '../utils/format';
import type { ApiSettings } from '../types/settings';

interface SettingsContextValue {
  settings: ApiSettings | null;
  loading: boolean;
  reload: () => Promise<void>;
  applySettings: (settings: ApiSettings) => void;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [settings, setSettings] = useState<ApiSettings | null>(null);
  const [loading, setLoading] = useState(false);

  const applySettings = useCallback((next: ApiSettings) => {
    setSettings(next);
    configureCurrency({
      code: next.currency_code,
      symbol: next.currency_symbol,
      locale: next.currency_locale,
      decimals: next.decimal_places,
    });
  }, []);

  const reload = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const next = await getSettings();
      applySettings(next);
    } catch {
      // La configuración no debe bloquear la operación; se usan valores por defecto.
    } finally {
      setLoading(false);
    }
  }, [user, applySettings]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const value = useMemo(
    () => ({ settings, loading, reload, applySettings }),
    [settings, loading, reload, applySettings],
  );

  return (
    <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
  );
}

export function useSettings(): SettingsContextValue {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings debe usarse dentro de SettingsProvider');
  }
  return context;
}
