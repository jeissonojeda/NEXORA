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
import LoadingState from '../../components/ui/LoadingState';
import Modal from '../../components/ui/Modal';
import Pagination from '../../components/ui/Pagination';
import PageHeader from '../../components/ui/PageHeader';
import Icon from '../../components/ui/Icon';
import { formatCurrency, formatDateTime } from '../../utils/format';

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
    <div className="animate-fade-in space-y-5">
      <PageHeader
        title="Compras"
        subtitle="Gestiona las compras a tus proveedores."
        actions={
          canWrite && (
            <button
              type="button"
              onClick={() => {
                setNewSupplierId('');
                setNewNotes('');
                setFormError(null);
                setCreateOpen(true);
              }}
              className="nx-btn nx-btn-primary"
            >
              <Icon name="plus" size={16} />
              Nueva compra
            </button>
          )
        }
      />

      {/* Filtros */}
      <div className="nx-card grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label htmlFor="purchase-status" className="nx-label">
            Estado
          </label>
          <select
            id="purchase-status"
            value={statusFilter}
            onChange={changeFilter((value) =>
              setStatusFilter(value as '' | PurchaseStatus),
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
          <label htmlFor="purchase-supplier" className="nx-label">
            Proveedor
          </label>
          <select
            id="purchase-supplier"
            value={supplierFilter}
            onChange={changeFilter((value) => setSupplierFilter(value))}
            className="nx-select"
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
          <label htmlFor="purchase-from" className="nx-label">
            Fecha inicial
          </label>
          <input
            id="purchase-from"
            type="date"
            value={dateFrom}
            onChange={changeFilter((value) => setDateFrom(value))}
            className="nx-input"
          />
        </div>
        <div>
          <label htmlFor="purchase-to" className="nx-label">
            Fecha final
          </label>
          <input
            id="purchase-to"
            type="date"
            value={dateTo}
            onChange={changeFilter((value) => setDateTo(value))}
            className="nx-input"
          />
        </div>
      </div>

      {purchasesState.error && <ErrorAlert message={purchasesState.error} />}

      {/* Tabla */}
      <div className="nx-card overflow-hidden">
        {purchasesState.loading ? (
          <div className="p-5">
            <LoadingState rows={6} />
          </div>
        ) : total === 0 ? (
          <EmptyState title="Sin compras" hint="Aún no hay compras registradas." icon="cart" />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="nx-table">
                <thead>
                  <tr>
                    <th>Número</th>
                    <th>Proveedor</th>
                    <th className="hidden md:table-cell">Fecha</th>
                    <th>Estado</th>
                    <th className="text-right">Total</th>
                    <th className="text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {purchasesState.data?.items.map((purchase) => (
                    <tr key={purchase.id}>
                      <td className="font-mono text-xs font-medium text-foreground">
                        {purchase.purchase_number}
                      </td>
                      <td className="text-foreground">{purchase.supplier.name}</td>
                      <td className="hidden text-muted md:table-cell">
                        {formatDateTime(purchase.created_at)}
                      </td>
                      <td>
                        <Badge tone={STATUS_TONE[purchase.status]}>
                          {purchaseStatusLabel(purchase.status)}
                        </Badge>
                      </td>
                      <td className="text-right font-medium text-foreground">
                        {formatCurrency(purchase.total)}
                      </td>
                      <td className="whitespace-nowrap text-right">
                        <Link
                          to={`/purchases/${purchase.id}`}
                          className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                        >
                          <Icon name="eye" size={14} />
                          Ver
                        </Link>
                        {canWrite && purchase.status === 'DRAFT' && (
                          <button
                            type="button"
                            onClick={() => {
                              setCancelError(null);
                              setCancelling(purchase);
                            }}
                            className="nx-btn nx-btn-sm nx-btn-ghost text-red-600 dark:text-red-400"
                          >
                            <Icon name="trash" size={14} />
                            Cancelar
                          </button>
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

      {/* Modal nueva compra */}
      <Modal
        open={createOpen}
        title="Nueva compra (borrador)"
        onClose={() => setCreateOpen(false)}
      >
        <div className="space-y-4">
          <div>
            <label htmlFor="draft-supplier" className="nx-label">
              Proveedor *
            </label>
            <select
              id="draft-supplier"
              value={newSupplierId}
              onChange={(event) => setNewSupplierId(event.target.value)}
              className="nx-select"
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
            <label htmlFor="draft-notes" className="nx-label">
              Notas
            </label>
            <textarea
              id="draft-notes"
              rows={2}
              value={newNotes}
              onChange={(event) => setNewNotes(event.target.value)}
              className="nx-input"
            />
          </div>
          {formError && (
            <p className="rounded-md border border-red-300 bg-red-100/60 px-3 py-2 text-sm text-red-800 dark:bg-red-500/10 dark:text-red-300">
              {formError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setCreateOpen(false)}
              className="nx-btn nx-btn-secondary"
              disabled={busy}
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => void handleCreateDraft()}
              disabled={busy}
              className="nx-btn nx-btn-primary disabled:opacity-60"
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
