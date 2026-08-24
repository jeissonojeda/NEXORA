import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import {
  createCustomer,
  deactivateCustomer,
  listCustomers,
  updateCustomer,
} from '../../services/customers';
import type { ApiCustomer, CustomerFormValues } from '../../types/customer';
import { formatCurrency } from '../../utils/format';
import { ROUTES } from '../../routes';
import CustomerForm from '../../components/domain/CustomerForm';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import Modal from '../../components/ui/Modal';
import Pagination from '../../components/ui/Pagination';

const inputClass =
  'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none';

const PAGE_SIZE = 10;

export default function CustomersPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const roles = user?.roles.map((role) => role.name) ?? [];
  const canWrite =
    roles.some((role) =>
      ['ADMIN', 'INVENTORY_MANAGER', 'CASHIER'].includes(role),
    ) ?? false;
  const canDelete = roles.includes('ADMIN');

  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [creditFilter, setCreditFilter] = useState('all');
  const [page, setPage] = useState(1);

  const customersState = useAsync(
    () =>
      listCustomers({
        q: query || null,
        isActive:
          statusFilter === 'all' ? null : statusFilter === 'active',
        creditEnabled:
          creditFilter === 'all' ? null : creditFilter === 'credit',
        orderBy: 'name',
        order: 'asc',
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [query, statusFilter, creditFilter, page],
  );

  useEffect(() => {
    const timer = setTimeout(() => setQuery(searchInput.trim()), 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  function changeStatus(value: string) {
    setStatusFilter(value);
    setPage(1);
  }

  function changeCredit(value: string) {
    setCreditFilter(value);
    setPage(1);
  }

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ApiCustomer | null>(null);
  const [deactivating, setDeactivating] = useState<ApiCustomer | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deactivateError, setDeactivateError] = useState<string | null>(null);

  async function handleSubmit(values: CustomerFormValues) {
    setBusy(true);
    setFormError(null);
    try {
      if (editing) {
        await updateCustomer(editing.id, values);
      } else {
        await createCustomer(values);
      }
      setFormOpen(false);
      setEditing(null);
      await customersState.reload();
    } catch (err) {
      setFormError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmDeactivate() {
    if (!deactivating) return;
    setBusy(true);
    setDeactivateError(null);
    try {
      await deactivateCustomer(deactivating.id);
      setDeactivating(null);
      await customersState.reload();
    } catch (err) {
      setDeactivateError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const total = customersState.data?.total ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-gray-900">Clientes</h2>
        {canWrite && (
          <button
            type="button"
            onClick={() => {
              setEditing(null);
              setFormError(null);
              setFormOpen(true);
            }}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            + Nuevo cliente
          </button>
        )}
      </div>

      {/* Filtros */}
      <div className="grid grid-cols-1 gap-3 rounded-lg bg-white p-4 shadow sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2">
          <label htmlFor="customer-search" className="block text-xs font-medium text-gray-500">
            Buscar por nombre, identificación, email o teléfono
          </label>
          <input
            id="customer-search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Ej. Juan Pérez, 1090…, juan@…"
            className={`mt-1 ${inputClass}`}
          />
        </div>
        <div>
          <label htmlFor="customer-status" className="block text-xs font-medium text-gray-500">
            Estado
          </label>
          <select
            id="customer-status"
            value={statusFilter}
            onChange={(event) => changeStatus(event.target.value)}
            className={`mt-1 ${inputClass}`}
          >
            <option value="all">Todos</option>
            <option value="active">Activos</option>
            <option value="inactive">Inactivos</option>
          </select>
        </div>
        <div>
          <label htmlFor="customer-credit" className="block text-xs font-medium text-gray-500">
            Crédito
          </label>
          <select
            id="customer-credit"
            value={creditFilter}
            onChange={(event) => changeCredit(event.target.value)}
            className={`mt-1 ${inputClass}`}
          >
            <option value="all">Todos</option>
            <option value="credit">Con crédito</option>
            <option value="no-credit">Sin crédito</option>
          </select>
        </div>
      </div>

      <ErrorAlert
        message={customersState.error}
        onRetry={
          customersState.loading ? undefined : () => void customersState.reload()
        }
      />

      <div className="overflow-hidden rounded-lg bg-white shadow">
        {customersState.loading ? (
          <p className="px-4 py-10 text-center text-sm text-gray-500">Cargando…</p>
        ) : total === 0 ? (
          <EmptyState
            title="Sin clientes"
            hint="Ajusta la búsqueda o crea el primer cliente."
          />
        ) : (
          <>
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Nombre</th>
                  <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">
                    Identificación
                  </th>
                  <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">
                    Teléfono
                  </th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">
                    Saldo actual
                  </th>
                  <th className="hidden px-4 py-3 text-right font-semibold text-gray-600 sm:table-cell">
                    Disponible
                  </th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Crédito</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Estado</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {customersState.data?.items.map((customer) => (
                  <tr key={customer.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{customer.name}</td>
                    <td className="hidden px-4 py-3 font-mono text-xs text-gray-500 md:table-cell">
                      {customer.identification || '—'}
                    </td>
                    <td className="hidden px-4 py-3 text-gray-600 md:table-cell">
                      {customer.phone || '—'}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-gray-800">
                      {formatCurrency(customer.current_balance)}
                    </td>
                    <td className="hidden px-4 py-3 text-right tabular-nums text-gray-800 sm:table-cell">
                      {customer.credit_enabled
                        ? formatCurrency(customer.credit_available)
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {customer.credit_enabled ? (
                        <Badge tone="blue">Con crédito</Badge>
                      ) : (
                        <Badge tone="gray">Contado</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {customer.is_active ? (
                        <Badge tone="green">Activo</Badge>
                      ) : (
                        <Badge tone="red">Inactivo</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => navigate(`${ROUTES.CUSTOMERS}/${customer.id}`)}
                        className="mr-2 text-sm font-medium text-gray-600 hover:text-gray-800"
                      >
                        Ver
                      </button>
                      {canWrite && (
                        <>
                          <button
                            type="button"
                            onClick={() => {
                              setEditing(customer);
                              setFormError(null);
                              setFormOpen(true);
                            }}
                            className="mr-2 text-sm font-medium text-blue-600 hover:text-blue-800"
                          >
                            Editar
                          </button>
                          {canDelete && customer.is_active && (
                            <button
                              type="button"
                              onClick={() => {
                                setDeactivateError(null);
                                setDeactivating(customer);
                              }}
                              className="text-sm font-medium text-red-600 hover:text-red-800"
                            >
                              Desactivar
                            </button>
                          )}
                        </>
                      )}
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

      <Modal
        open={formOpen}
        wide
        title={editing ? `Editar cliente: ${editing.name}` : 'Nuevo cliente'}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
        }}
      >
        <CustomerForm
          key={editing?.id ?? 'new'}
          initial={
            editing
              ? {
                  name: editing.name,
                  identification: editing.identification ?? '',
                  phone: editing.phone ?? '',
                  email: editing.email ?? '',
                  address: editing.address ?? '',
                  city: editing.city ?? '',
                  notes: editing.notes ?? '',
                  credit_enabled: editing.credit_enabled,
                  credit_limit: editing.credit_enabled
                    ? String(Number(editing.credit_limit))
                    : '',
                }
              : undefined
          }
          busy={busy}
          error={formError}
          submitLabel={editing ? 'Guardar cambios' : 'Crear cliente'}
          onSubmit={(values) => void handleSubmit(values)}
        />
      </Modal>

      <ConfirmDialog
        open={deactivating !== null}
        title="Desactivar cliente"
        message={`¿Desactivar "${deactivating?.name}"? No podrá usarse en ventas futuras, pero su historial de cuentas y pagos se conserva íntegro.`}
        confirmLabel="Desactivar"
        destructive
        busy={busy}
        error={deactivateError}
        onConfirm={() => void confirmDeactivate()}
        onCancel={() => setDeactivating(null)}
      />

      {formError && !formOpen && <ErrorAlert message={formError} />}
    </div>
  );
}
