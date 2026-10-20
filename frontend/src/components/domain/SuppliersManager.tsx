import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import {
  createSupplier,
  deactivateSupplier,
  getSupplier,
  listSuppliers,
  updateSupplier,
} from '../../services/suppliers';
import { listPurchases } from '../../services/purchases';
import type {
  ApiSupplier,
  ApiSupplierDetail,
  SupplierFormValues,
} from '../../types/catalog';
import type { PurchaseStatus } from '../../types/purchase';
import { purchaseStatusLabel } from '../../types/purchase';
import { userHasPermission } from '../../utils/permissions';
import { formatCurrency, formatDateTime } from '../../utils/format';
import SupplierDetailModal from './SupplierDetailModal';
import SupplierForm from './SupplierForm';
import Badge from '../ui/Badge';
import ConfirmDialog from '../ui/ConfirmDialog';
import EmptyState from '../ui/EmptyState';
import ErrorAlert from '../ui/ErrorAlert';
import LoadingState from '../ui/LoadingState';
import Modal from '../ui/Modal';
import Pagination from '../ui/Pagination';
import Icon from '../ui/Icon';

const PAGE_SIZE = 10;

const STATUS_TONE: Record<PurchaseStatus, 'gray' | 'green' | 'red'> = {
  DRAFT: 'gray',
  CONFIRMED: 'green',
  CANCELLED: 'red',
};

interface SuppliersManagerProps {
  onChanged?: () => void;
}

export default function SuppliersManager({ onChanged }: SuppliersManagerProps) {
  const { user } = useAuth();
  const canWrite =
    userHasPermission(user, 'suppliers.create') ||
    userHasPermission(user, 'suppliers.update');

  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(1);

  const suppliersState = useAsync(
    () =>
      listSuppliers({
        q: query || null,
        isActive: statusFilter === 'all' ? null : statusFilter === 'active',
        orderBy: 'name',
        order: 'asc',
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [query, statusFilter, page],
  );

  useEffect(() => {
    const timer = setTimeout(() => setQuery(searchInput.trim()), 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [createKey, setCreateKey] = useState(0);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ApiSupplier | null>(null);
  const [detail, setDetail] = useState<ApiSupplierDetail | null>(null);
  const [deactivating, setDeactivating] = useState<ApiSupplier | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deactivateError, setDeactivateError] = useState<string | null>(null);

  const [historySupplier, setHistorySupplier] = useState<ApiSupplier | null>(null);
  const historyState = useAsync(
    () =>
      historySupplier
        ? listPurchases({ supplierId: historySupplier.id, limit: 20 })
        : Promise.resolve({ items: [], total: 0 }),
    [historySupplier?.id],
  );

  async function reload() {
    await suppliersState.reload();
    onChanged?.();
  }

  async function handleCreate(values: SupplierFormValues) {
    setCreateBusy(true);
    setCreateError(null);
    try {
      await createSupplier(values);
      setCreateSuccess(`Proveedor "${values.name.trim()}" registrado.`);
      setCreateKey((key) => key + 1);
      await reload();
      onChanged?.();
    } catch (err) {
      setCreateError(extractErrorMessage(err));
    } finally {
      setCreateBusy(false);
    }
  }

  async function handleEdit(values: SupplierFormValues) {
    if (!editing) return;
    setBusy(true);
    setFormError(null);
    try {
      await updateSupplier(editing.id, values);
      setFormOpen(false);
      setEditing(null);
      await reload();
    } catch (err) {
      setFormError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function openDetail(supplier: ApiSupplier) {
    try {
      const loaded = await getSupplier(supplier.id);
      setDetail(loaded);
    } catch (err) {
      setFormError(extractErrorMessage(err));
    }
  }

  async function confirmDeactivate() {
    if (!deactivating) return;
    setBusy(true);
    setDeactivateError(null);
    try {
      await deactivateSupplier(deactivating.id);
      setDeactivating(null);
      await reload();
    } catch (err) {
      setDeactivateError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const total = suppliersState.data?.total ?? 0;

  return (
    <div className="space-y-4">
      {createSuccess && (
        <div
          role="status"
          className="flex items-center justify-between gap-3 rounded-lg border border-emerald-300 bg-emerald-100/60 px-4 py-2.5 text-sm text-emerald-900 dark:bg-emerald-500/10 dark:text-emerald-200"
        >
          <span className="flex items-center gap-2">
            <Icon name="check" size={16} />
            {createSuccess}
          </span>
          <button
            type="button"
            onClick={() => setCreateSuccess(null)}
            className="text-xs font-semibold hover:underline"
          >
            Cerrar
          </button>
        </div>
      )}

      {canWrite && (
        <div className="nx-card p-5">
          <h3 className="mb-3 text-sm font-bold uppercase tracking-widest text-faint">
            Registrar proveedor
          </h3>
          <SupplierForm
            key={createKey}
            busy={createBusy}
            error={createError}
            submitLabel="Registrar proveedor"
            onSubmit={(values) => void handleCreate(values)}
          />
        </div>
      )}

      {/* Filtros */}
      <div className="nx-card grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2 lg:col-span-3">
          <label htmlFor="sup-search" className="nx-label">
            Buscar por nombre, identificación, email o teléfono
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint">
              <Icon name="search" size={16} />
            </span>
            <input
              id="sup-search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Ej. Distribuidora, 3101234, ventas@…"
              className="nx-input pl-9"
            />
          </div>
        </div>
        <div>
          <label htmlFor="sup-status" className="nx-label">
            Estado
          </label>
          <select
            id="sup-status"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setPage(1);
            }}
            className="nx-select"
          >
            <option value="all">Todos</option>
            <option value="active">Activos</option>
            <option value="inactive">Inactivos</option>
          </select>
        </div>
      </div>

      <ErrorAlert
        message={suppliersState.error}
        onRetry={suppliersState.loading ? undefined : () => void suppliersState.reload()}
      />

      <div className="nx-card overflow-hidden">
        {suppliersState.loading ? (
          <div className="p-5">
            <LoadingState rows={6} />
          </div>
        ) : total === 0 ? (
          <EmptyState
            title="Sin proveedores"
            hint="Registra un proveedor con el formulario de arriba."
            icon="store"
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="nx-table">
                <thead>
                  <tr>
                    <th>Proveedor</th>
                    <th className="hidden md:table-cell">Contacto</th>
                    <th className="hidden sm:table-cell">Teléfono</th>
                    <th className="text-right">Productos</th>
                    <th>Estado</th>
                    <th className="text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliersState.data?.items.map((supplier) => (
                    <tr key={supplier.id}>
                      <td>
                        <p className="font-medium text-foreground">{supplier.name}</p>
                        {supplier.identification && (
                          <p className="font-mono text-xs text-faint">
                            {supplier.identification}
                          </p>
                        )}
                      </td>
                      <td className="hidden text-muted md:table-cell">
                        {supplier.contact_name || supplier.email || '—'}
                      </td>
                      <td className="hidden text-muted sm:table-cell">
                        {supplier.phone || '—'}
                      </td>
                      <td className="text-right text-foreground">
                        {supplier.products_count}
                      </td>
                      <td>
                        {supplier.is_active ? (
                          <Badge tone="green">Activo</Badge>
                        ) : (
                          <Badge tone="red">Inactivo</Badge>
                        )}
                      </td>
                      <td className="whitespace-nowrap text-right">
                        <button
                          type="button"
                          onClick={() => setHistorySupplier(supplier)}
                          className="nx-btn nx-btn-sm nx-btn-ghost text-muted"
                        >
                          <Icon name="receipt" size={14} />
                          Historial
                        </button>
                        <button
                          type="button"
                          onClick={() => void openDetail(supplier)}
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
                                setEditing(supplier);
                                setFormError(null);
                                setFormOpen(true);
                              }}
                              className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                            >
                              <Icon name="pencil" size={14} />
                              Editar
                            </button>
                            {supplier.is_active && (
                              <button
                                type="button"
                                onClick={() => {
                                  setDeactivateError(null);
                                  setDeactivating(supplier);
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

      {/* Editar proveedor */}
      <Modal
        open={formOpen}
        wide
        title={editing ? `Editar proveedor: ${editing.name}` : 'Nuevo proveedor'}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
        }}
      >
        <SupplierForm
          key={editing?.id ?? 'new'}
          initial={
            editing
              ? {
                  name: editing.name,
                  identification: editing.identification ?? '',
                  contact_name: editing.contact_name ?? '',
                  phone: editing.phone ?? '',
                  email: editing.email ?? '',
                  address: editing.address ?? '',
                  city: editing.city ?? '',
                  notes: editing.notes ?? '',
                }
              : undefined
          }
          busy={busy}
          error={formError}
          submitLabel="Guardar cambios"
          onSubmit={(values) => void handleEdit(values)}
        />
      </Modal>

      <ConfirmDialog
        open={deactivating !== null}
        title="Desactivar proveedor"
        message={`¿Desactivar "${deactivating?.name}"? Sus productos asociados permanecen intactos.`}
        confirmLabel="Desactivar"
        destructive
        busy={busy}
        error={deactivateError}
        onConfirm={() => void confirmDeactivate()}
        onCancel={() => setDeactivating(null)}
      />

      <SupplierDetailModal
        supplier={detail}
        onClose={() => setDetail(null)}
      />

      {/* Historial de compras del proveedor */}
      <Modal
        open={historySupplier !== null}
        wide
        title={`Compras de ${historySupplier?.name ?? ''}`}
        onClose={() => setHistorySupplier(null)}
      >
        {historyState.loading ? (
          <LoadingState rows={4} />
        ) : (historyState.data?.total ?? 0) === 0 ? (
          <EmptyState
            title="Sin compras"
            hint="Este proveedor aún no tiene compras registradas."
            icon="receipt"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="nx-table">
              <thead>
                <tr>
                  <th>Número</th>
                  <th className="hidden sm:table-cell">Fecha</th>
                  <th>Estado</th>
                  <th className="text-right">Total</th>
                  <th className="text-right">Ver</th>
                </tr>
              </thead>
              <tbody>
                {historyState.data?.items.map((purchase) => (
                  <tr key={purchase.id}>
                    <td className="font-mono text-xs text-foreground">
                      {purchase.purchase_number}
                    </td>
                    <td className="hidden text-muted sm:table-cell">
                      {formatDateTime(purchase.created_at)}
                    </td>
                    <td>
                      <Badge tone={STATUS_TONE[purchase.status]}>
                        {purchaseStatusLabel(purchase.status)}
                      </Badge>
                    </td>
                    <td className="text-right tabular-nums text-foreground">
                      {formatCurrency(purchase.total)}
                    </td>
                    <td className="text-right">
                      <Link
                        to={`/purchases/${purchase.id}`}
                        className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                      >
                        Abrir
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Modal>

    </div>
  );
}
