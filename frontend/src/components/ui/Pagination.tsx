import Icon from './Icon';

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export default function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-4">
      <p className="text-sm text-muted">
        Mostrando <span className="font-semibold text-foreground">{from}–{to}</span> de{' '}
        <span className="font-semibold text-foreground">{total}</span> registros
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          className="nx-btn nx-btn-sm nx-btn-secondary"
        >
          <Icon name="chevron-left" size={14} />
          Anterior
        </button>
        <span className="min-w-20 text-center text-sm text-muted">
          {page} / {totalPages}
        </span>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
          className="nx-btn nx-btn-sm nx-btn-secondary"
        >
          Siguiente
          <Icon name="chevron-right" size={14} />
        </button>
      </div>
    </div>
  );
}