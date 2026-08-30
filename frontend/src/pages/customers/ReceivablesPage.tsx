import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAsync } from '../../hooks/useAsync';
import { listReceivables } from '../../services/receivables';
import {
  receivableStatusLabel,
} from '../../types/customer';
import type { ReceivableStatus } from '../../types/customer';
import { formatCurrency, formatDateTime } from '../../utils/format';
import { ROUTES } from '../../routes';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import LoadingState from '../../components/ui/LoadingState';
import Pagination from '../../components/ui/Pagination';
import PageHeader from '../../components/ui/PageHeader';
import Icon from '../../components/ui/Icon';

const PAGE_SIZE = 10;

const STATUS_OPTIONS: { value: '' | ReceivableStatus; label: string }[] = [
  { value: '', label: 'Todos los estados' },
  { value: 'OPEN', label: 'Pendientes' },
  { value: 'PARTIALLY_PAID', label: 'Abonadas' },
  { value: 'PAID', label: 'Pagadas' },
  { value: 'CANCELLED', label: 'Anuladas' },
];

function statusTone(status: ReceivableStatus): 'green' | 'amber' | 'red' | 'gray' {
  switch (status) {
    case 'OPEN':
      return 'red';
    case 'PARTIALLY_PAID':
      return 'amber';
    case 'PAID':
      return 'green';
    default:
      return 'gray';
  }
}

export default function ReceivablesPage() {
  const [status, setStatus] = useState<'' | ReceivableStatus>('');
  const [page, setPage] = useState(1);

  const state = useAsync(
    () =>
      listReceivables({
        status: status || null,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [status, page],
  );

  const total = state.data?.total ?? 0;

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Cuentas por cobrar"
        subtitle="Créditos otorgados a clientes y sus abonos."
        actions={
          <Link to={ROUTES.CUSTOMERS} className="nx-btn nx-btn-secondary">
            <Icon name="users" size={16} />
            Ver clientes
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label htmlFor="filter-status" className="nx-label mb-0">
          Estado
        </label>
        <select
          id="filter-status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value as '' | ReceivableStatus);
            setPage(1);
          }}
          className="nx-select w-auto"
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <ErrorAlert
        message={state.error}
        onRetry={state.loading ? undefined : () => void state.reload()}
      />

      <div className="nx-card overflow-hidden">
        {state.loading ? (
          <div className="p-5">
            <LoadingState rows={6} />
          </div>
        ) : total === 0 ? (
          <EmptyState
            title="Sin cuentas por cobrar"
            hint={
              status
                ? 'Ajusta el filtro o regresa a "Todos los estados".'
                : 'Las ventas a crédito generan cuentas por cobrar automáticamente.'
            }
            icon="banknote"
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="nx-table">
                <thead>
                  <tr>
                    <th>Cliente</th>
                    <th className="hidden sm:table-cell">Descripción</th>
                    <th className="hidden md:table-cell">Vencimiento</th>
                    <th className="hidden lg:table-cell text-right">Original</th>
                    <th className="hidden lg:table-cell text-right">Pagado</th>
                    <th className="text-right">Saldo</th>
                    <th>Estado</th>
                    <th className="text-right">Ver</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data?.items.map((account) => (
                    <tr key={account.id}>
                      <td>
                        <Link
                          to={`${ROUTES.CUSTOMERS}/${account.customer_id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {account.customer.name}
                        </Link>
                      </td>
                      <td className="hidden max-w-[220px] truncate text-muted sm:table-cell">
                        {account.description || '—'}
                      </td>
                      <td className="hidden text-muted md:table-cell">
                        {account.due_date ? formatDateTime(account.due_date) : '—'}
                      </td>
                      <td className="hidden text-right text-muted lg:table-cell">
                        {formatCurrency(account.original_amount)}
                      </td>
                      <td className="hidden text-right text-muted lg:table-cell">
                        {formatCurrency(account.paid_amount)}
                      </td>
                      <td
                        className={`text-right font-bold ${
                          Number(account.balance) > 0 ? 'text-red-600 dark:text-red-400' : 'text-muted'
                        }`}
                      >
                        {formatCurrency(account.balance)}
                      </td>
                      <td>
                        <Badge tone={statusTone(account.status)}>
                          {receivableStatusLabel(account.status)}
                        </Badge>
                      </td>
                      <td className="text-right">
                        <Link
                          to={`${ROUTES.CUSTOMERS}/${account.customer_id}`}
                          className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                          aria-label={`Ver detalles de ${account.customer.name}`}
                        >
                          <Icon name="eye" size={14} />
                          Detalle
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={total}
              onChange={setPage}
            />
          </>
        )}
      </div>

      <p className="mt-3 text-xs text-faint">
        Los abonos se registran desde el detalle de cada cliente.
      </p>
    </div>
  );
}