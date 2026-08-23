import { useState, type ChangeEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import {
  cancelPurchase,
  createPurchase,
  listPurchases,
} from '../../services/purchases';
import { listSuppliers } from '../../services/suppliers';
import type {
  ApiPurchase,
  PurchaseStatus,
} from '../../types/purchase';
import { purchaseStatusLabel } from '../../types/purchase';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import Modal from '../../components/ui/Modal';
import Pagination from '../../components/ui/Pagination';
import { formatCurrency, formatDateTime } from '../../utils/format';

const inputClass =
  'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none';

const PAGE_SIZE = 10;

const STATUS_TONE: Record<PurchaseStatus, 'gray' | 'green' | 'red'> = {
  DRAFT: 'gray',
  CONFIRMED: 'green',
  CANCELLED: 'red',
};

export default function PurchasesPage() {
  const { user } = useAuth();
  const canWrite =
    user?.roles.some((role) =>
      ['ADMIN', 'INVENTORY_MANAGER'].includes(role.name),
    ) ?? false;
  const navigate = useNavigate();

  const [statusFilter, setStatusFilter] = useState<'' | PurchaseStatus>('');
  const [supplierFilter, setSupplierFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);

  const purchasesState = useAsync(
    () =>
      listPurchases({
        status: statusFilter || null,
        supplierId: supplierFilter || null,
        dateFrom: dateFrom ? `${dateFrom}T00:00:00` : null,
        dateTo: dateTo ? `${dateTo}T23:59:59` : null,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [statusFilter, supplierFilter, dateFrom, dateTo, page],
  );

  const suppliersState = useAsync(
    () => listSuppliers({ limit: 200 }),
    [],
  );

  function changeFilter(
    setter: (value: string) => void,
  ): (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void {
    return (event) => {
      setter(event.target.value);
      setPage(1);
    };
  }

  // Crear borrador
  const [createOpen, setCreateOpen] = useState(false);
  const [newSupplierId, setNewSupplierId] = useState('');
  const [newNotes, setNewNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Cancelar
  const [cancelling, setCancelling] = useState<ApiPurchase | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);

  async function handleCreateDraft() {
    if (!newSupplierId) {
      setFormError('Seleccione un proveedor');
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      const created = await createPurchase({
        supplier_id: newSupplierId,
        notes: newNotes.trim() || null,
      });
      setCreateOpen(false);
      navigate(`/purchases/${created.id}`);
    } catch (err) {
      setFormError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmCancel() {
    if (!cancelling) return;
    setBusy(true);
    setCancelError(null);
    try {
      await cancelPurchase(cancelling.id);
      setCancelling(null);
      await purchasesState.reload();
    } catch (err) {
      setCancelError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const total = purchasesState.data?.total ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-gray-900">Compras</h2>
        {canWrite && (
          <button
            type="button"
            onClick={() => {
              setNewSupplierId('');
              setNewNotes('');
              setFormError(null);
              setCreateOpen(true);
            }}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            + Nueva compra
          </button>
        )}
      </div>

      {/* Filtros */}
      <div className="grid grid-cols-1 gap-3 rounded-lg bg-white p-4 shadow sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <label htmlFor="purchase-status" className="block text-xs font-medium text-gray-500">
            Estado
          </label>
          <select
            id="purchase-status"
            value={statusFilter}
            onChange={changeFilter((value) =>
              setStatusFilter(value as '' | PurchaseStatus),
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
          <label htmlFor="purchase-supplier" className="block text-xs font-medium text-gray-500">
            Proveedor
          </label>
          <select
            id="purchase-supplier"
            value={supplierFilter}
            onChange={changeFilter((value) => setSupplierFilter(value))}
            className={`mt-1 ${inputClass}`}
          >
            <option value="">Todos</option>
            {suppliersState.data?.items.map((supplier) => (
              <option key={supplier.id} value={supplier.id}>
                {supplier.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="purchase-from" className="block text-xs font-medium text-gray-500">
            Fecha inicial
          </label>
          <input
            id="purchase-from"
            type="date"
            value={dateFrom}
            onChange={changeFilter((value) => setDateFrom(value))}
            className={`mt-1 ${inputClass}`}
          />
        </div>
        <div>
          <label htmlFor="purchase-to" className="block text-xs font-medium text-gray-500">
            Fecha final
          </label>
          <input
            id="purchase-to"
            type="date"
            value={dateTo}
            onChange={changeFilter((value) => setDateTo(value))}
            className={`mt-1 ${inputClass}`}
          />
        </div>
      </div>

      {purchasesState.error && <ErrorAlert message={purchasesState.error} />}

      {/* Tabla */}
      <div className="overflow-hidden rounded-lg bg-white shadow">
        {purchasesState.loading ? (
          <p className="px-4 py-10 text-center text-sm text-gray-500">Cargando compras…</p>
        ) : total === 0 ? (
          <EmptyState title="Sin compras" hint="Aún no hay compras registradas." />
        ) : (
          <>
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Número</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Proveedor</th>
                  <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">
                    Fecha
                  </th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Estado</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Total</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {purchasesState.data?.items.map((purchase) => (
                  <tr key={purchase.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs font-medium text-gray-900">
                      {purchase.purchase_number}
                    </td>
                    <td className="px-4 py-3 text-gray-800">{purchase.supplier.name}</td>
                    <td className="hidden px-4 py-3 text-gray-600 md:table-cell">
                      {formatDateTime(purchase.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={STATUS_TONE[purchase.status]}>
                        {purchaseStatusLabel(purchase.status)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900">
                      {formatCurrency(purchase.total)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right">
                      <Link
                        to={`/purchases/${purchase.id}`}
                        className="mr-2 text-sm font-medium text-blue-600 hover:text-blue-800"
                      >
                        Ver
                      </Link>
                      {canWrite && purchase.status === 'DRAFT' && (
                        <button
                          type="button"
                          onClick={() => {
                            setCancelError(null);
                            setCancelling(purchase);
                          }}
                          className="text-sm font-medium text-red-600 hover:text-red-800"
                        >
                          Cancelar
                        </button>
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

      {/* Modal nueva compra */}
      <Modal
        open={createOpen}
        title="Nueva compra (borrador)"
        onClose={() => setCreateOpen(false)}
      >
        <div className="space-y-4">
          <div>
            <label htmlFor="draft-supplier" className="block text-sm font-medium text-gray-700">
              Proveedor *
            </label>
            <select
              id="draft-supplier"
              value={newSupplierId}
              onChange={(event) => setNewSupplierId(event.target.value)}
              className={`mt-1 ${inputClass}`}
            >
              <option value="">Seleccione…</option>
              {suppliersState.data?.items
                .filter((supplier) => supplier.is_active)
                .map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.name}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label htmlFor="draft-notes" className="block text-sm font-medium text-gray-700">
              Notas
            </label>
            <textarea
              id="draft-notes"
              rows={2}
              value={newNotes}
              onChange={(event) => setNewNotes(event.target.value)}
              className={`mt-1 ${inputClass}`}
            />
          </div>
          {formError && (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {formError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setCreateOpen(false)}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              disabled={busy}
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => void handleCreateDraft()}
              disabled={busy}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {busy ? 'Guardando…' : 'Guardar borrador'}
            </button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={cancelling !== null}
        title="Cancelar compra"
        message={`¿Cancelar la compra ${cancelling?.purchase_number ?? ''}? La compra quedará en estado CANCELLED y no podrá confirmarse.`}
        destructive
        busy={busy}
        error={cancelError}
        onConfirm={() => void confirmCancel()}
        onCancel={() => setCancelling(null)}
      />
    </div>
  );
}
