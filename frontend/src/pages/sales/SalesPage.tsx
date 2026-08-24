import { useState, type ChangeEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useAsync } from '../../hooks/useAsync';
import { listSales } from '../../services/sales';
import type { SaleStatus } from '../../types/sale';
import { salePaymentMethodLabel, saleStatusLabel } from '../../types/sale';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import Pagination from '../../components/ui/Pagination';
import { formatCurrency, formatDateTime } from '../../utils/format';

const inputClass =
  'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none';

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
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);

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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-gray-900">Ventas</h2>
        {canSell && (
          <Link
            to="/pos"
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            + Nueva venta
          </Link>
        )}
      </div>

      {/* Filtros */}
      <div className="grid grid-cols-1 gap-3 rounded-lg bg-white p-4 shadow sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label htmlFor="sale-status" className="block text-xs font-medium text-gray-500">
            Estado
          </label>
          <select
            id="sale-status"
            value={statusFilter}
            onChange={changeFilter((value) =>
              setStatusFilter(value as '' | SaleStatus),
            )}
            className={`mt-1 ${inputClass}`}
          >
            <option value="">Todos</option>
            <option value="DRAFT">Borrador</option>
            <option value="CONFIRMED">Confirmada</option>
            <option value="CANCELLED">Cancelada</option>
          </select>
        </div>
        <div>
          <label htmlFor="sale-search" className="block text-xs font-medium text-gray-500">
            Número de venta
          </label>
          <input
            id="sale-search"
            type="text"
            placeholder="Buscar…"
            value={search}
            onChange={changeFilter(setSearch)}
            className={`mt-1 ${inputClass}`}
          />
        </div>
        <div>
          <label htmlFor="sale-from" className="block text-xs font-medium text-gray-500">
            Fecha inicial
          </label>
          <input
            id="sale-from"
            type="date"
            value={dateFrom}
            onChange={changeFilter((value) => setDateFrom(value))}
            className={`mt-1 ${inputClass}`}
          />
        </div>
        <div>
          <label htmlFor="sale-to" className="block text-xs font-medium text-gray-500">
            Fecha final
          </label>
          <input
            id="sale-to"
            type="date"
            value={dateTo}
            onChange={changeFilter((value) => setDateTo(value))}
            className={`mt-1 ${inputClass}`}
          />
        </div>
      </div>

      {salesState.error && <ErrorAlert message={salesState.error} />}

      <div className="overflow-hidden rounded-lg bg-white shadow">
        {salesState.loading ? (
          <p className="px-4 py-10 text-center text-sm text-gray-500">
            Cargando ventas…
          </p>
        ) : total === 0 ? (
          <EmptyState
            title="Sin ventas"
            hint="Aún no hay ventas registradas."
          />
        ) : (
          <>
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Número</th>
                  <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">
                    Fecha
                  </th>
                  <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 lg:table-cell">
                    Cliente
                  </th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Pago</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Estado</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Total</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {salesState.data?.items.map((sale) => (
                  <tr key={sale.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs font-medium text-gray-900">
                      {sale.sale_number}
                    </td>
                    <td className="hidden px-4 py-3 text-gray-600 md:table-cell">
                      {formatDateTime(sale.created_at)}
                    </td>
                    <td className="hidden px-4 py-3 text-gray-600 lg:table-cell">
                      {sale.customer?.name ?? 'Consumidor final'}
                    </td>
                    <td className="px-4 py-3 text-gray-800">
                      {salePaymentMethodLabel(sale.payment_method)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={STATUS_TONE[sale.status]}>
                        {saleStatusLabel(sale.status)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900">
                      {formatCurrency(sale.total)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right">
                      <Link
                        to={`/ventas/${sale.id}`}
                        className="text-sm font-medium text-blue-600 hover:text-blue-800"
                      >
                        Ver
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
