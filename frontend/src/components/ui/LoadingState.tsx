interface LoadingStateProps {
  rows?: number;
  className?: string;
}

export default function LoadingState({ rows = 5, className = '' }: LoadingStateProps) {
  return (
    <div className={`space-y-3 ${className}`} aria-label="Cargando">
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="h-11 animate-pulse rounded-lg bg-surface-2"
          style={{ animationDelay: `${index * 60}ms` }}
        />
      ))}
    </div>
  );
}