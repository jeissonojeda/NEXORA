import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { AuthUser } from '../types/auth';
import {
  clearStoredToken,
  getStoredToken,
  getCurrentUser,
  login as apiLogin,
  logout as apiLogout,
} from '../services/auth';

interface AuthContextValue {
  user: AuthUser | null;
  initializing: boolean;
  authenticating: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [authenticating, setAuthenticating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function restoreSession() {
      if (!getStoredToken()) {
        setInitializing(false);
        return;
      }
      try {
        const current = await getCurrentUser();
        if (!cancelled) setUser(current);
      } catch {
        clearStoredToken();
      } finally {
        if (!cancelled) setInitializing(false);
      }
    }
    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setAuthenticating(true);
    setError(null);
    try {
      await apiLogin({ username, password });
      const current = await getCurrentUser();
      setUser(current);
      return true;
    } catch (err) {
      const detail =
        err &&
        typeof err === 'object' &&
        'response' in err &&
        typeof (err as { response?: { data?: { detail?: unknown } } }).response
          ?.data?.detail === 'string'
          ? (err as { response: { data: { detail: string } } }).response.data
              .detail
          : 'No se pudo iniciar sesión';
      setError(detail);
      return false;
    } finally {
      setAuthenticating(false);
    }
  }, []);

  const logout = useCallback(() => {
    void apiLogout();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, initializing, authenticating, error, login, logout }),
    [user, initializing, authenticating, error, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de AuthProvider');
  }
  return context;
}
