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
import Modal from '../../components/ui/Modal';
import Pagination from '../../components/ui/Pagination';

const inputClass =
  'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none';

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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-gray-900">Proveedores</h2>
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
            + Nuevo proveedor
          </button>
        )}
      </div>

      {/* Filtros */}
      <div className="grid grid-cols-1 gap-3 rounded-lg bg-white p-4 shadow sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2 lg:col-span-3">
          <label htmlFor="supplier-search" className="block text-xs font-medium text-gray-500">
            Buscar por nombre, identificación, email o teléfono
          </label>
          <input
            id="supplier-search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Ej. Distribuidora, 3101234, ventas@… , 8888-"
            className={`mt-1 ${inputClass}`}
          />
        </div>
        <div>
          <label htmlFor="supplier-status" className="block text-xs font-medium text-gray-500">
            Estado
          </label>
          <select
            id="supplier-status"
            value={statusFilter}
            onChange={(event) => changeStatus(event.target.value)}
            className={`mt-1 ${inputClass}`}
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

      <div className="overflow-hidden rounded-lg bg-white shadow">
        {suppliersState.loading ? (
          <p className="px-4 py-10 text-center text-sm text-gray-500">Cargando…</p>
        ) : total === 0 ? (
          <EmptyState
            title="Sin proveedores"
            hint="Ajusta la búsqueda o crea el primer proveedor."
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
                    Contacto / Teléfono
                  </th>
                  <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 lg:table-cell">
                    Email
                  </th>
                  <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 sm:table-cell">
                    Ciudad
                  </th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Productos</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Estado</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {suppliersState.data?.items.map((supplier) => (
                  <tr key={supplier.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{supplier.name}</td>
                    <td className="hidden px-4 py-3 font-mono text-xs text-gray-500 md:table-cell">
                      {supplier.identification || '—'}
                    </td>
                    <td className="hidden px-4 py-3 text-gray-600 md:table-cell">
                      {supplier.contact_name || '—'}
                      {supplier.phone && (
                        <span className="ml-1 text-xs text-gray-400">· {supplier.phone}</span>
                      )}
                    </td>
                    <td className="hidden max-w-[180px] truncate px-4 py-3 text-gray-600 lg:table-cell">
                      {supplier.email || '—'}
                    </td>
                    <td className="hidden px-4 py-3 text-gray-600 sm:table-cell">
                      {supplier.city || '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-800">
                      {supplier.products_count}
                    </td>
                    <td className="px-4 py-3">
                      {supplier.is_active ? (
                        <Badge tone="green">Activo</Badge>
                      ) : (
                        <Badge tone="red">Inactivo</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => void openDetail(supplier)}
                        className="mr-2 text-sm font-medium text-gray-600 hover:text-gray-800"
                      >
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
                            className="mr-2 text-sm font-medium text-blue-600 hover:text-blue-800"
                          >
                            Editar
                          </button>
                          {supplier.is_active && (
                            <button
                              type="button"
                              onClick={() => {
                                setDeactivateError(null);
                                setDeactivating(supplier);
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
        title={editing ? `Editar proveedor: ${editing.name}` : 'Nuevo proveedor'}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
        }}
      >
        {editing && canWrite && (
          <div className="mb-4 flex items-center justify-between rounded-md bg-gray-50 px-3 py-2 text-sm">
            <span>Estado actual:</span>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void updateSupplier(editing.id, { is_active: !editing.is_active }).then(
                  () => suppliersState.reload(),
                )
              }
              className="font-medium text-blue-600 hover:text-blue-800"
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
