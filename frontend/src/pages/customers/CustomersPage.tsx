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
import Icon from '../../components/ui/Icon';
import LoadingState from '../../components/ui/LoadingState';
import Modal from '../../components/ui/Modal';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';

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
    <div className="animate-fade-in space-y-5">
      <PageHeader
        title="Clientes"
        subtitle="Gestiona tus clientes y sus cuentas por cobrar."
        actions={
          canWrite && (
            <button
              type="button"
              onClick={() => {
                setEditing(null);
                setFormError(null);
                setFormOpen(true);
              }}
              className="nx-btn nx-btn-primary"
            >
              <Icon name="plus" size={16} />
              Nuevo cliente
            </button>
          )
        }
      />

      {/* Filtros */}
      <div className="nx-card grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2">
          <label htmlFor="customer-search" className="nx-label">
            Buscar (nombre, identificación, email o teléfono)
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint">
              <Icon name="search" size={16} />
            </span>
            <input
              id="customer-search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Ej. Juan Pérez, 1090…, juan@…"
              className="nx-input pl-9"
            />
          </div>
        </div>
        <div>
          <label htmlFor="customer-status" className="nx-label">
            Estado
          </label>
          <select
            id="customer-status"
            value={statusFilter}
            onChange={(event) => changeStatus(event.target.value)}
            className="nx-select"
          >
            <option value="all">Todos</option>
            <option value="active">Activos</option>
            <option value="inactive">Inactivos</option>
          </select>
        </div>
        <div>
          <label htmlFor="customer-credit" className="nx-label">
            Crédito
          </label>
          <select
            id="customer-credit"
            value={creditFilter}
            onChange={(event) => changeCredit(event.target.value)}
            className="nx-select"
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

      <div className="nx-card overflow-hidden">
        {customersState.loading ? (
          <div className="p-5">
            <LoadingState rows={6} />
          </div>
        ) : total === 0 ? (
          <EmptyState
            title="Sin clientes"
            hint="Ajusta la búsqueda o crea el primer cliente."
            icon="users"
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="nx-table">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th className="hidden md:table-cell">Identificación</th>
                    <th className="hidden md:table-cell">Teléfono</th>
                    <th className="text-right">Saldo actual</th>
                    <th className="hidden text-right sm:table-cell">Disponible</th>
                    <th>Crédito</th>
                    <th>Estado</th>
                    <th className="text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {customersState.data?.items.map((customer) => (
                    <tr key={customer.id}>
                      <td className="font-medium text-foreground">{customer.name}</td>
                      <td className="hidden font-mono text-xs text-muted md:table-cell">
                        {customer.identification || '—'}
                      </td>
                      <td className="hidden text-muted md:table-cell">
                        {customer.phone || '—'}
                      </td>
                      <td className="text-right tabular-nums text-foreground">
                        {formatCurrency(customer.current_balance)}
                      </td>
                      <td className="hidden text-right tabular-nums text-foreground sm:table-cell">
                        {customer.credit_enabled
                          ? formatCurrency(customer.credit_available)
                          : '—'}
                      </td>
                      <td>
                        {customer.credit_enabled ? (
                          <Badge tone="blue">Con crédito</Badge>
                        ) : (
                          <Badge tone="gray">Contado</Badge>
                        )}
                      </td>
                      <td>
                        {customer.is_active ? (
                          <Badge tone="green">Activo</Badge>
                        ) : (
                          <Badge tone="red">Inactivo</Badge>
                        )}
                      </td>
                      <td className="whitespace-nowrap text-right">
                        <button
                          type="button"
                          onClick={() => navigate(`${ROUTES.CUSTOMERS}/${customer.id}`)}
                          className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                        >
                          <Icon name="eye" size={14} />
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
                              className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                            >
                              <Icon name="pencil" size={14} />
                              Editar
                            </button>
                            {canDelete && customer.is_active && (
                              <button
                                type="button"
                                onClick={() => {
                                  setDeactivateError(null);
                                  setDeactivating(customer);
                                }}
                                className="nx-btn nx-btn-sm nx-btn-ghost text-red-600 dark:text-red-400"
                              >
                                <Icon name="trash" size={14} />
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