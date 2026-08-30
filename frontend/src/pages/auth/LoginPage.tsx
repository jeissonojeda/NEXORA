import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { ROUTES } from '../../routes';
import ErrorAlert, { InlineError } from '../../components/ui/ErrorAlert';
import Icon from '../../components/ui/Icon';
import ThemeToggle from '../../components/ui/ThemeToggle';

const FEATURES = [
  {
    icon: 'chart-bar' as const,
    title: 'Decisiones con datos',
    description: 'Reportes y análisis en tiempo real de tu operación.',
  },
  {
    icon: 'bag' as const,
    title: 'Punto de venta ágil',
    description: 'Cobros por efectivo, tarjeta, transferencia o crédito.',
  },
  {
    icon: 'layers' as const,
    title: 'Inventario bajo control',
    description: 'Kardex, alertas de stock bajo y compras inteligentes.',
  },
];

export default function LoginPage() {
  const { login, authenticating, error } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!username.trim()) {
      setFormError('Escribe tu nombre de usuario.');
      return;
    }
    if (!password) {
      setFormError('Escribe tu contraseña.');
      return;
    }
    setFormError(null);
    const success = await login(username.trim(), password);
    if (success) {
      const origin = (location.state as { from?: string } | null)?.from;
      navigate(origin ?? ROUTES.HOME, { replace: true });
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* Panel de marca */}
      <div className="relative hidden flex-1 flex-col justify-between overflow-hidden nx-brand-gradient p-10 text-white lg:flex">
        <div className="absolute -right-24 -top-24 h-80 w-80 rounded-full bg-white/10" />
        <div className="absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-white/10" />
        <div className="relative">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/20 backdrop-blur">
              <Icon name="sparkles" size={24} />
            </span>
            <div>
              <p className="text-2xl font-extrabold tracking-tight">NEXORA</p>
              <p className="text-xs font-medium text-white/80">
                Gestión inteligente de tu negocio
              </p>
            </div>
          </div>
        </div>

        <div className="relative max-w-md">
          <h2 className="text-4xl font-extrabold leading-tight tracking-tight">
            Tu negocio, impulsado por datos e inteligencia artificial.
          </h2>
          <p className="mt-4 text-white/80">
            Facturación, inventario, crédito a clientes, caja y reportes en un
            solo lugar.
          </p>
          <ul className="mt-8 space-y-4">
            {FEATURES.map((feature) => (
              <li key={feature.title} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15 backdrop-blur">
                  <Icon name={feature.icon} size={18} />
                </span>
                <div>
                  <p className="font-semibold">{feature.title}</p>
                  <p className="text-sm text-white/75">{feature.description}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-white/70">
          © {new Date().getFullYear()} NEXORA · Fase 11 — Optimización y mejoras
        </p>
      </div>

      {/* Formulario */}
      <div className="flex w-full flex-col items-center justify-center bg-[var(--nx-bg)] px-4 py-10 lg:w-[480px] lg:shrink-0">
        <div className="mb-6 flex w-full max-w-sm items-center justify-between lg:hidden">
          <div className="flex items-center gap-2.5">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl nx-brand-gradient text-white shadow-md">
              <Icon name="sparkles" size={21} />
            </span>
            <span className="text-xl font-extrabold tracking-tight text-foreground">
              NEXORA
            </span>
          </div>
          <ThemeToggle />
        </div>

        <div className="w-full max-w-sm animate-slide-up">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Bienvenido de nuevo
          </h1>
          <p className="mt-1 text-sm text-muted">
            Inicia sesión para continuar a tu panel de control.
          </p>

          <form onSubmit={(event) => void handleSubmit(event)} className="mt-8 space-y-5">
            <div>
              <label htmlFor="login-username" className="nx-label">
                Usuario
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint">
                  <Icon name="user" size={18} />
                </span>
                <input
                  id="login-username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  autoFocus
                  className="nx-input pl-10"
                  placeholder="tu.usuario"
                />
              </div>
            </div>

            <div>
              <label htmlFor="login-password" className="nx-label">
                Contraseña
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint">
                  <Icon name="lock" size={18} />
                </span>
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  className="nx-input pl-10"
                  placeholder="••••••••"
                />
              </div>
            </div>

            {formError && <InlineError message={formError} />}
            <ErrorAlert message={error} />

            <button
              type="submit"
              disabled={authenticating}
              className="nx-btn nx-btn-primary w-full py-3"
            >
              {authenticating ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  Ingresando…
                </>
              ) : (
                'Ingresar'
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-xs text-faint">
            Acceso restringido · Sistema de facturación e inventario
          </p>
        </div>
      </div>
    </div>
  );
}