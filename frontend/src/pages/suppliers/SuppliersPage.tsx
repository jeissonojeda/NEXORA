import { useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import {
  createSupplier,
  deactivateSupplier,
  getSupplier,
  listSuppliers,
  updateSupplier,
} from '../../services/suppliers';
import type { ApiSupplier, ApiSupplierDetail, SupplierFormValues } from '../../types/catalog';
import SupplierDetailModal from '../../components/domain/SupplierDetailModal';
import SupplierForm from '../../components/domain/SupplierForm';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import LoadingState from '../../components/ui/LoadingState';
import Modal from '../../components/ui/Modal';
import Pagination from '../../components/ui/Pagination';
import PageHeader from '../../components/ui/PageHeader';
import Icon from '../../components/ui/Icon';

const PAGE_SIZE = 10;

export default function SuppliersPage() {
  const { user } = useAuth();
  const canWrite =
    user?.roles.some((role) =>
      ['ADMIN', 'INVENTORY_MANAGER'].includes(role.name),
    ) ?? false;

  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(1);

  const suppliersState = useAsync(
    () =>
      listSuppliers({
        q: query || null,
        isActive:
          statusFilter === 'all' ? null : statusFilter === 'active',
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

  function changeStatus(value: string) {
    setStatusFilter(value);
    setPage(1);
  }

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ApiSupplier | null>(null);
  const [detail, setDetail] = useState<ApiSupplierDetail | null>(null);
  const [deactivating, setDeactivating] = useState<ApiSupplier | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deactivateError, setDeactivateError] = useState<string | null>(null);

  async function openDetail(supplier: ApiSupplier) {
    try {
      const loaded = await getSupplier(supplier.id);
      setDetail(loaded);
    } catch (err) {
      setFormError(extractErrorMessage(err));
    }
  }

  async function handleSubmit(values: SupplierFormValues) {
    setBusy(true);
    setFormError(null);
    try {
      if (editing) {
        await updateSupplier(editing.id, values);
      } else {
        await createSupplier(values);
      }
      setFormOpen(false);
      setEditing(null);
      await suppliersState.reload();
    } catch (err) {
      setFormError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggleSupplierStatus() {
    if (!editing) return;
    setBusy(true);
    setFormError(null);
    try {
      await updateSupplier(editing.id, { is_active: !editing.is_active });
      setEditing({ ...editing, is_active: !editing.is_active });
      await suppliersState.reload();
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
      await deactivateSupplier(deactivating.id);
      setDeactivating(null);
      await suppliersState.reload();
    } catch (err) {
      setDeactivateError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const total = suppliersState.data?.total ?? 0;

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        title="Proveedores"
        subtitle="Administra tus proveedores, contactos y datos de facturación."
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
              Nuevo proveedor
            </button>
          )
        }
      />

      {/* Filtros */}
      <div className="nx-card grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2 lg:col-span-3">
          <label htmlFor="supplier-search" className="nx-label">
            Buscar por nombre, identificación, email o teléfono
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint">
              <Icon name="search" size={16} />
            </span>
            <input
              id="supplier-search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Ej. Distribuidora, 3101234, ventas@… , 8888-"
              className="nx-input pl-9"
            />
          </div>
        </div>
        <div>
          <label htmlFor="supplier-status" className="nx-label">
            Estado
          </label>
          <select
            id="supplier-status"
            value={statusFilter}
            onChange={(event) => changeStatus(event.target.value)}
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
        onRetry={
          suppliersState.loading ? undefined : () => void suppliersState.reload()
        }
      />

      <div className="nx-card overflow-hidden">
        {suppliersState.loading ? (
          <div className="p-5">
            <LoadingState rows={6} />
          </div>
        ) : total === 0 ? (
          <EmptyState
            title="Sin proveedores"
            hint="Ajusta la búsqueda o crea el primer proveedor."
            icon="truck"
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="nx-table">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th className="hidden md:table-cell">Identificación</th>
                    <th className="hidden md:table-cell">Contacto / Teléfono</th>
                    <th className="hidden lg:table-cell">Email</th>
                    <th className="hidden sm:table-cell">Ciudad</th>
                    <th className="text-right">Productos</th>
                    <th>Estado</th>
                    <th className="text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliersState.data?.items.map((supplier) => (
                    <tr key={supplier.id}>
                      <td className="font-medium text-foreground">{supplier.name}</td>
                      <td className="hidden font-mono text-xs text-muted md:table-cell">
                        {supplier.identification || '—'}
                      </td>
                      <td className="hidden text-muted md:table-cell">
                        {supplier.contact_name || '—'}
                        {supplier.phone && (
                          <span className="ml-1 text-xs text-faint">· {supplier.phone}</span>
                        )}
                      </td>
                      <td className="hidden max-w-[180px] truncate text-muted lg:table-cell">
                        {supplier.email || '—'}
                      </td>
                      <td className="hidden text-muted sm:table-cell">
                        {supplier.city || '—'}
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

      <Modal
        open={formOpen}
        wide
        title={editing ? `Editar proveedor: ${editing.name}` : 'Nuevo proveedor'}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
        }}
      >
        {editing && canWrite && (
          <div className="mb-4 flex items-center justify-between rounded-lg bg-surface-2 px-3 py-2 text-sm">
            <span className="text-muted">Estado actual:</span>
            <button
              type="button"
              disabled={busy}
              onClick={() => void toggleSupplierStatus()}
              className="font-medium text-primary hover:brightness-75"
            >
              {editing.is_active ? 'Desactivar' : 'Activar'}
            </button>
          </div>
        )}
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
          submitLabel={editing ? 'Guardar cambios' : 'Crear proveedor'}
          onSubmit={(values) => void handleSubmit(values)}
        />
      </Modal>

      <ConfirmDialog
        open={deactivating !== null}
        title="Desactivar proveedor"
        message={`¿Desactivar "${deactivating?.name}"? Sus productos asociados permanecen intactos; un proveedor nunca se elimina físicamente.`}
        confirmLabel="Desactivar"
        destructive
        busy={busy}
        error={deactivateError}
        onConfirm={() => void confirmDeactivate()}
        onCancel={() => setDeactivating(null)}
      />

      <SupplierDetailModal
        supplier={detail}
        onClose={() => {
          setDetail(null);
          setPage(1);
        }}
      />

      {formError && !formOpen && (
        <ErrorAlert message={formError} />
      )}
    </div>
  );
}
