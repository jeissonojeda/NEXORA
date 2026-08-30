import Icon from './Icon';

interface ErrorAlertProps {
  message: string | null;
  onRetry?: () => void;
}

export default function ErrorAlert({ message, onRetry }: ErrorAlertProps) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="flex items-center justify-between gap-3 rounded-xl border border-red-300 bg-red-100/60 px-4 py-3 text-sm text-red-800 dark:bg-red-500/10 dark:text-red-300"
    >
      <span className="flex items-center gap-2">
        <Icon name="triangle-alert" size={18} />
        <span>{message}</span>
      </span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 font-semibold underline hover:no-underline"
        >
          Reintentar
        </button>
      )}
    </div>
  );
}

export function InlineError({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-1 flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
      <Icon name="triangle-alert" size={13} />
      {message}
    </p>
  );
}