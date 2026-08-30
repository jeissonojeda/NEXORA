import { useEffect, useState, type ChangeEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useAsync } from '../../hooks/useAsync';
import { listSales } from '../../services/sales';
import type { SaleStatus } from '../../types/sale';
import { salePaymentMethodLabel, saleStatusLabel } from '../../types/sale';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import Icon from '../../components/ui/Icon';
import LoadingState from '../../components/ui/LoadingState';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import { formatCurrency, formatDateTime } from '../../utils/format';

const PAGE_SIZE = 10;

const STATUS_TONE: Record<SaleStatus, 'gray' | 'green' | 'red'> = {
  DRAFT: 'gray',
  CONFIRMED: 'green',
  CANCELLED: 'red',
};

export default function SalesPage() {
  const { user } = useAuth();
  const canSell =
    user?.roles.some((role) => ['ADMIN', 'CASHIER'].includes(role.name)) ??
    false;

  const [statusFilter, setStatusFilter] = useState<'' | SaleStatus>('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const salesState = useAsync(
    () =>
      listSales({
        status: statusFilter || null,
        q: search || null,
        dateFrom: dateFrom ? `${dateFrom}T00:00:00` : null,
        dateTo: dateTo ? `${dateTo}T23:59:59` : null,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [statusFilter, search, dateFrom, dateTo, page],
  );

  function changeFilter(
    setter: (value: string) => void,
  ): (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void {
    return (event) => {
      setter(event.target.value);
      setPage(1);
    };
  }

  const total = salesState.data?.total ?? 0;

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        title="Ventas"
        subtitle="Historial de ventas y estado de cada operación."
        actions={
          canSell && (
            <Link to="/pos" className="nx-btn nx-btn-primary">
              <Icon name="plus" size={16} />
              Nueva venta
            </Link>
          )
        }
      />

      {/* Filtros */}
      <div className="nx-card grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label htmlFor="sale-status" className="nx-label">
            Estado
          </label>
          <select
            id="sale-status"
            value={statusFilter}
            onChange={changeFilter((value) =>
              setStatusFilter(value as '' | SaleStatus),
            )}
            className="nx-select"
          >
            <option value="">Todos</option>
            <option value="DRAFT">Borrador</option>
            <option value="CONFIRMED">Confirmada</option>
            <option value="CANCELLED">Cancelada</option>
          </select>
        </div>
        <div>
          <label htmlFor="sale-search" className="nx-label">
            Número de venta
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint">
              <Icon name="search" size={16} />
            </span>
            <input
              id="sale-search"
              type="text"
              placeholder="Buscar…"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              className="nx-input pl-9"
            />
          </div>
        </div>
        <div>
          <label htmlFor="sale-from" className="nx-label">
            Fecha inicial
          </label>
          <input
            id="sale-from"
            type="date"
            value={dateFrom}
            onChange={changeFilter((value) => setDateFrom(value))}
            className="nx-input"
          />
        </div>
        <div>
          <label htmlFor="sale-to" className="nx-label">
            Fecha final
          </label>
          <input
            id="sale-to"
            type="date"
            value={dateTo}
            onChange={changeFilter((value) => setDateTo(value))}
            className="nx-input"
          />
        </div>
      </div>

      {salesState.error && <ErrorAlert message={salesState.error} />}

      <div className="nx-card overflow-hidden">
        {salesState.loading ? (
          <div className="p-5">
            <LoadingState rows={6} />
          </div>
        ) : total === 0 ? (
          <EmptyState
            title="Sin ventas"
            hint="Aún no hay ventas registradas."
            icon="cart"
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="nx-table">
                <thead>
                  <tr>
                    <th>Número</th>
                    <th className="hidden md:table-cell">Fecha</th>
                    <th className="hidden lg:table-cell">Cliente</th>
                    <th>Pago</th>
                    <th>Estado</th>
                    <th className="text-right">Total</th>
                    <th className="text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {salesState.data?.items.map((sale) => (
                    <tr key={sale.id}>
                      <td className="font-mono text-xs font-medium text-foreground">
                        {sale.sale_number}
                      </td>
                      <td className="hidden text-muted md:table-cell">
                        {formatDateTime(sale.created_at)}
                      </td>
                      <td className="hidden text-muted lg:table-cell">
                        {sale.customer?.name ?? 'Consumidor final'}
                      </td>
                      <td className="text-foreground">
                        {salePaymentMethodLabel(sale.payment_method)}
                      </td>
                      <td>
                        <Badge tone={STATUS_TONE[sale.status]}>
                          {saleStatusLabel(sale.status)}
                        </Badge>
                      </td>
                      <td className="text-right font-medium text-foreground">
                        {formatCurrency(sale.total)}
                      </td>
                      <td className="whitespace-nowrap text-right">
                        <Link
                          to={`/ventas/${sale.id}`}
                          className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                        >
                          <Icon name="eye" size={14} />
                          Ver
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
    </div>
  );
}