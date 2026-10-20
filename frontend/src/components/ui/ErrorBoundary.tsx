import { Component, type ErrorInfo, type ReactNode } from 'react';
import Icon from './Icon';

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Título mostrado al usuario. */
  title?: string;
  /** Mensaje descriptivo mostrado al usuario. */
  description?: string;
  /** Etiqueta del botón de reintento. Si se omite, no se muestra. */
  retryLabel?: string;
  /**
   * Acción de reintento. Si se omite, se reintenta volviendo a montar el
   * subárbol (reset interno del estado del boundary).
   */
  onRetry?: () => void;
  /** Acción secundaria (p. ej. "Volver a productos"). */
  onSecondary?: () => void;
  secondaryLabel?: string;
  /** Identificador para los logs (módulo afectado). */
  context?: string;
  /** Muestra el detalle técnico del error (útil en desarrollo). */
  showDetails?: boolean;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Barrera de errores de React.
 *
 * Evita que una excepción durante el render de un módulo destruya toda la
 * aplicación (pantalla negra). Muestra un mensaje amigable, registra el error
 * para desarrollo y ofrece reintentar / volver.
 */
export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Registro útil para desarrollo (no se oculta silenciosamente).
    console.error(
      `[ErrorBoundary${this.props.context ? `:${this.props.context}` : ''}]`,
      error,
      info.componentStack,
    );
  }

  private handleRetry = (): void => {
    this.setState({ error: null });
    this.props.onRetry?.();
  };

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    const {
      title = 'Se produjo un error inesperado en esta pantalla.',
      description = 'Puedes reintentar la operación o volver a la pantalla anterior. El resto de la aplicación sigue funcionando.',
      retryLabel = 'Reintentar',
      onRetry,
      onSecondary,
      secondaryLabel,
      showDetails = false,
    } = this.props;

    return (
      <div
        role="alert"
        className="flex flex-col items-center justify-center gap-4 rounded-xl border border-red-300 bg-red-50 px-6 py-10 text-center dark:border-red-500/40 dark:bg-red-500/10"
      >
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300">
          <Icon name="triangle-alert" size={24} />
        </span>
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-red-800 dark:text-red-300">
            {title}
          </h3>
          <p className="max-w-md text-sm text-red-700 dark:text-red-200/80">
            {description}
          </p>
        </div>
        {showDetails && error.message && (
          <pre className="max-w-md overflow-auto rounded bg-red-100/70 px-3 py-2 text-left text-xs text-red-800 dark:bg-red-500/10 dark:text-red-200">
            {error.message}
          </pre>
        )}
        <div className="flex flex-wrap items-center justify-center gap-2">
          {(onRetry || retryLabel) && (
            <button
              type="button"
              onClick={this.handleRetry}
              className="nx-btn nx-btn-primary"
            >
              <Icon name="refresh" size={16} />
              {retryLabel}
            </button>
          )}
          {onSecondary && (
            <button
              type="button"
              onClick={onSecondary}
              className="nx-btn nx-btn-secondary"
            >
              {secondaryLabel ?? 'Volver'}
            </button>
          )}
        </div>
      </div>
    );
  }
}
