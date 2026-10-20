import { useState } from 'react';
import { useLicense } from '../../contexts/LicenseContext';
import {
  activateLicense,
  createManualRequest,
  importManualResponse,
} from '../../services/license';
import { InlineError } from '../../components/ui/ErrorAlert';
import Icon from '../../components/ui/Icon';
import ThemeToggle from '../../components/ui/ThemeToggle';

type Mode = 'online' | 'manual';

function extractError(err: unknown, fallback: string): string {
  if (
    err &&
    typeof err === 'object' &&
    'response' in err &&
    typeof (err as { response?: { data?: { detail?: unknown } } }).response?.data
      ?.detail === 'string'
  ) {
    return (err as { response: { data: { detail: string } } }).response.data.detail;
  }
  return fallback;
}

export default function ActivationPage() {
  const { status, refresh } = useLicense();
  const [mode, setMode] = useState<Mode>('online');
  const [licenseKey, setLicenseKey] = useState('');
  const [manualKey, setManualKey] = useState('');
  const [requestCode, setRequestCode] = useState('');
  const [responseCode, setResponseCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function handleOnline(event: React.FormEvent) {
    event.preventDefault();
    if (!licenseKey.trim()) {
      setError('Ingresa el código de licencia.');
      return;
    }
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await activateLicense(licenseKey.trim());
      await refresh();
      setNotice('Licencia activada correctamente.');
    } catch (err) {
      setError(extractError(err, 'No se pudo activar la licencia.'));
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateRequest(event: React.FormEvent) {
    event.preventDefault();
    if (!manualKey.trim()) {
      setError('Ingresa el código de licencia.');
      return;
    }
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const code = await createManualRequest(manualKey.trim());
      setRequestCode(code);
      setNotice('Solicitud generada. Envíala a tu proveedor.');
    } catch (err) {
      setError(extractError(err, 'No se pudo generar la solicitud.'));
    } finally {
      setBusy(false);
    }
  }

  async function handleImport(event: React.FormEvent) {
    event.preventDefault();
    if (!responseCode.trim()) {
      setError('Pega el código de respuesta.');
      return;
    }
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await importManualResponse(responseCode.trim());
      await refresh();
      setNotice('Licencia activada correctamente.');
    } catch (err) {
      setError(extractError(err, 'No se pudo importar la respuesta.'));
    } finally {
      setBusy(false);
    }
  }

  async function copyRequest() {
    try {
      await navigator.clipboard.writeText(requestCode);
      setNotice('Solicitud copiada al portapapeles.');
    } catch {
      setError('No se pudo copiar automáticamente. Copia el texto manualmente.');
    }
  }

  const statusMessage = status?.message ?? null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--nx-bg)] px-4 py-10">
      <div className="w-full max-w-lg">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl nx-brand-gradient text-white shadow-md">
              <Icon name="shield" size={21} />
            </span>
            <span className="text-xl font-extrabold tracking-tight text-foreground">
              NEXORA
            </span>
          </div>
          <ThemeToggle />
        </div>

        <div className="nx-card p-6 animate-slide-up">
          <h1 className="text-xl font-bold tracking-tight text-foreground">
            Activación de licencia
          </h1>
          <p className="mt-1 text-sm text-muted">
            Activa este sistema para continuar. Puedes hacerlo por internet o de
            forma manual (sin conexión).
          </p>

          {statusMessage && (
            <div className="mt-4 rounded-xl border border-amber-300/60 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
              {statusMessage}
            </div>
          )}
          {status?.installation_id && (
            <p className="mt-2 break-all text-xs text-faint">
              ID de instalación: {status.installation_id}
            </p>
          )}

          <div className="mt-5 flex gap-2 rounded-xl bg-[var(--nx-surface-2)] p-1">
            <button
              type="button"
              onClick={() => setMode('online')}
              className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition ${
                mode === 'online'
                  ? 'bg-[var(--nx-surface)] text-foreground shadow-sm'
                  : 'text-muted hover:text-foreground'
              }`}
            >
              Por internet
            </button>
            <button
              type="button"
              onClick={() => setMode('manual')}
              className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition ${
                mode === 'manual'
                  ? 'bg-[var(--nx-surface)] text-foreground shadow-sm'
                  : 'text-muted hover:text-foreground'
              }`}
            >
              Manual (sin conexión)
            </button>
          </div>

          {mode === 'online' ? (
            <form onSubmit={(event) => void handleOnline(event)} className="mt-5 space-y-4">
              <div>
                <label htmlFor="license-key" className="nx-label">
                  Código de licencia
                </label>
                <input
                  id="license-key"
                  value={licenseKey}
                  onChange={(event) => setLicenseKey(event.target.value)}
                  className="nx-input"
                  placeholder="NEXORA-XXXX-XXXX-XXXX"
                />
              </div>
              <button
                type="submit"
                disabled={busy}
                className="nx-btn nx-btn-primary w-full py-3"
              >
                {busy ? 'Activando…' : 'Activar'}
              </button>
            </form>
          ) : (
            <div className="mt-5 space-y-6">
              <form
                onSubmit={(event) => void handleGenerateRequest(event)}
                className="space-y-4"
              >
                <div>
                  <label htmlFor="manual-key" className="nx-label">
                    Código de licencia
                  </label>
                  <input
                    id="manual-key"
                    value={manualKey}
                    onChange={(event) => setManualKey(event.target.value)}
                    className="nx-input"
                    placeholder="NEXORA-XXXX-XXXX-XXXX"
                  />
                </div>
                <button
                  type="submit"
                  disabled={busy}
                  className="nx-btn nx-btn-outline w-full"
                >
                  Paso 1: generar solicitud
                </button>
              </form>

              {requestCode && (
                <div>
                  <label htmlFor="request-code" className="nx-label">
                    Solicitud (envíala a tu proveedor)
                  </label>
                  <textarea
                    id="request-code"
                    readOnly
                    value={requestCode}
                    rows={4}
                    className="nx-input font-mono text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => void copyRequest()}
                    className="nx-btn nx-btn-ghost mt-2 text-sm"
                  >
                    <Icon name="download" size={16} /> Copiar solicitud
                  </button>
                </div>
              )}

              <form onSubmit={(event) => void handleImport(event)} className="space-y-4">
                <div>
                  <label htmlFor="response-code" className="nx-label">
                    Paso 2: código de respuesta
                  </label>
                  <textarea
                    id="response-code"
                    value={responseCode}
                    onChange={(event) => setResponseCode(event.target.value)}
                    rows={4}
                    className="nx-input font-mono text-xs"
                    placeholder="Pega aquí el código que te dio tu proveedor"
                  />
                </div>
                <button
                  type="submit"
                  disabled={busy}
                  className="nx-btn nx-btn-primary w-full py-3"
                >
                  {busy ? 'Activando…' : 'Activar licencia'}
                </button>
              </form>
            </div>
          )}

          {error && (
            <div className="mt-4">
              <InlineError message={error} />
            </div>
          )}
          {notice && (
            <p className="mt-4 rounded-xl border border-emerald-300/60 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
              {notice}
            </p>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-faint">
          NEXORA · Gestión inteligente de tu negocio
        </p>
      </div>
    </div>
  );
}
