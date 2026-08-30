import Icon from './Icon';

interface PageLoaderProps {
  message?: string;
}

export default function PageLoader({ message = 'Cargando…' }: PageLoaderProps) {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4">
      <div className="flex h-14 w-14 animate-pulse-soft items-center justify-center rounded-2xl nx-brand-gradient text-white shadow-lg">
        <Icon name="sparkles" size={26} />
      </div>
      <p className="text-sm font-medium text-muted">{message}</p>
    </div>
  );
}