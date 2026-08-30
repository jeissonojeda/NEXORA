import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import {
  addPurchaseItem,
  cancelPurchase,
  confirmPurchase,
  getPurchase,
  removePurchaseItem,
  updatePurchase,
  updatePurchaseItem,
} from '../../services/purchases';
import { listProducts } from '../../services/products';
import type { ApiProduct } from '../../types/catalog';
import type { ApiPurchaseItem, PurchaseStatus } from '../../types/purchase';
import { purchaseStatusLabel } from '../../types/purchase';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import LoadingState from '../../components/ui/LoadingState';
import Modal from '../../components/ui/Modal';
import PageHeader from '../../components/ui/PageHeader';
import Icon from '../../components/ui/Icon';
import { formatCurrency, formatDateTime } from '../../utils/format';

const STATUS_TONE: Record<PurchaseStatus, 'gray' | 'green' | 'red'> = {
  DRAFT: 'gray',
  CONFIRMED: 'green',
  CANCELLED: 'red',
};

interface ItemFormState {
  productId: string;
  quantity: string;
  unitCost: string;
  discount: string;
  tax: string;
}

const EMPTY_ITEM_FORM: ItemFormState = {
  productId: '',
  quantity: '',
  unitCost: '',
  discount: '0',
  tax: '0',
};

export default function PurchaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const canWrite =
    user?.roles.some((role) =>
      ['ADMIN', 'INVENTORY_MANAGER'].includes(role.name),
    ) ?? false;

  const purchaseState = useAsync(
    () => (id ? getPurchase(id) : Promise.resolve(null)),
    [id],
  );
  const productsState = useAsync(
    () => listProducts({ isActive: true, limit: 200 }),
    [],
  );

  const purchase = purchaseState.data;
  const isDraft = purchase?.status === 'DRAFT';
  const editable = Boolean(canWrite && isDraft);

  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Confirmar / cancelar compra
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);

  // Encabezado
  const [headerEditing, setHeaderEditing] = useState(false);
  const [headerDiscount, setHeaderDiscount] = useState('0');
  const [headerTax, setHeaderTax] = useState('0');
  const [headerNotes, setHeaderNotes] = useState('');

  // Ítems
  const [itemModalOpen, setItemModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<ApiPurchaseItem | null>(null);
  const [itemForm, setItemForm] = useState<ItemFormState>(EMPTY_ITEM_FORM);
  const [itemError, setItemError] = useState<string | null>(null);
  const [removingItem, setRemovingItem] = useState<ApiPurchaseItem | null>(
    null,
  );

  if (purchaseState.loading) {
    return (
      <div className="mx-auto max-w-2xl p-5">
        <LoadingState rows={6} />
      </div>
    );
  }
  if (!purchase) {
    return (
      <div className="animate-fade-in space-y-5">
        <PageHeader
          title="Compra no encontrada"
          subtitle="La compra solicitada no existe o fue eliminada."
        />
        <EmptyState
          title="Compra no encontrada"
          hint="La compra solicitada no existe o fue eliminada."
          icon="receipt"
        />
      </div>
    );
  }

  function setField(field: keyof ItemFormState, value: string) {
    setItemForm((previous) => ({ ...previous, [field]: value }));
  }

  async function runAction(action: () => Promise<unknown>) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      await purchaseState.reload();
      return true;
    } catch (err) {
      setActionError(extractErrorMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  }

  function openAddItem() {
    setItemForm(EMPTY_ITEM_FORM);
    setEditingItem(null);
    setItemError(null);
    setItemModalOpen(true);
  }

  function openEditItem(item: ApiPurchaseItem) {
    setItemForm({
      productId: item.product_id,
      quantity: String(item.quantity),
      unitCost: item.unit_cost,
      discount: item.discount,
      tax: item.tax,
    });
    setEditingItem(item);
    setItemError(null);
    setItemModalOpen(true);
  }

  function handleProductSelected(productId: string) {
    const product = productsState.data?.items.find(
      (candidate: ApiProduct) => candidate.id === productId,
    );
    setField('productId', productId);
    if (product && !editingItem) {
      setField('unitCost', product.purchase_price);
    }
  }

  function validateItemForm(): string | null {
    if (!itemForm.productId) return 'Seleccione un producto';
    const quantity = Number(itemForm.quantity);
    if (!Number.isInteger(quantity) || quantity <= 0) {
      return 'La cantidad debe ser un entero mayor que cero';
    }
    for (const [field, value] of [
      ['costo unitario', itemForm.unitCost],
      ['descuento', itemForm.discount || '0'],
      ['impuesto', itemForm.tax || '0'],
    ] as const) {
      const parsed = Number(value);
      if (Number.isNaN(parsed) || parsed < 0) {
        return `El ${field} debe ser un número ≥ 0`;
      }
    }
    return null;
  }

  async function submitItem() {
    const validationError = validateItemForm();
    if (validationError) {
      setItemError(validationError);
      return;
    }
    if (!id) return;
    const payload = {
      quantity: Number(itemForm.quantity),
      unit_cost: Number(itemForm.unitCost),
      discount: Number(itemForm.discount || '0'),
      tax: Number(itemForm.tax || '0'),
    };
    setBusy(true);
    setItemError(null);
    try {
      if (editingItem) {
        await updatePurchaseItem(id, editingItem.id, payload);
      } else {
        await addPurchaseItem(id, { product_id: itemForm.productId, ...payload });
      }
      setItemModalOpen(false);
      await purchaseState.reload();
    } catch (err) {
      setItemError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitHeader() {
    if (!id) return;
    const ok = await runAction(() =>
      updatePurchase(id, {
        notes: headerNotes.trim() || null,
        discount: Number(headerDiscount || '0'),
        tax: Number(headerTax || '0'),
      }),
    );
    if (ok) setHeaderEditing(false);
  }

  function openHeaderEdit() {
    setHeaderDiscount(purchase!.discount);
    setHeaderTax(purchase!.tax);
    setHeaderNotes(purchase!.notes ?? '');
    setActionError(null);
    setHeaderEditing(true);
  }

  const items = purchase.items;
  const hasItems = items.length > 0;

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        title={purchase.purchase_number}
        subtitle={
          <Link
            to="/purchases"
            className="inline-flex items-center gap-1 font-medium text-primary hover:brightness-75"
          >
            <Icon name="chevron-left" size={16} />
            Volver a compras
          </Link>
        }
        actions={
          <Badge tone={STATUS_TONE[purchase.status]}>
            {purchaseStatusLabel(purchase.status)}
          </Badge>
        }
      />

      {actionError && <ErrorAlert message={actionError} />}

      {/* Encabezado */}
      <div className="nx-card grid grid-cols-1 gap-4 p-4 md:grid-cols-2">
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Proveedor</dt>
            <dd className="font-medium text-foreground">{purchase.supplier.name}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Fecha de creación</dt>
            <dd className="text-foreground">{formatDateTime(purchase.created_at)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Creada por</dt>
            <dd className="text-foreground">{purchase.created_by_username ?? '—'}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted">Confirmada</dt>
            <dd className="text-foreground">
              {purchase.confirmed_at ? formatDateTime(purchase.confirmed_at) : '—'}
            </dd>
          </div>
          {!headerEditing && (
            <div className="flex justify-between gap-4">
              <dt className="text-muted">Notas</dt>
              <dd className="max-w-[60%] text-right text-foreground">
                {purchase.notes || '—'}
              </dd>
            </div>
          )}
        </dl>

        {/* Totales */}
        <div className="rounded-lg bg-surface-2 p-4 text-sm">
          <div className="flex justify-between py-1">
            <span className="text-muted">Subtotal</span>
            <span className="font-medium text-foreground">
              {formatCurrency(purchase.subtotal)}
            </span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-muted">Descuento</span>
            <span className="text-foreground">
              −{formatCurrency(purchase.discount)}
            </span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-muted">Impuesto</span>
            <span className="text-foreground">+{formatCurrency(purchase.tax)}</span>
          </div>
          <div className="mt-2 flex justify-between border-t border-line pt-2">
            <span className="font-semibold text-foreground">Total</span>
            <span className="text-lg font-bold text-foreground">
              {formatCurrency(purchase.total)}
            </span>
          </div>
          {editable && !headerEditing && (
            <button
              type="button"
              onClick={openHeaderEdit}
              className="mt-3 text-xs font-medium text-primary hover:brightness-75"
            >
              Editar descuento / impuesto / notas
            </button>
          )}
          {headerEditing && (
            <div className="mt-3 space-y-2">
              <div>
                <label htmlFor="header-discount" className="nx-label">
                  Descuento
                </label>
                <input
                  id="header-discount"
                  value={headerDiscount}
                  onChange={(event) => setHeaderDiscount(event.target.value)}
                  className="nx-input"
                />
              </div>
              <div>
                <label htmlFor="header-tax" className="nx-label">
                  Impuesto
                </label>
                <input
                  id="header-tax"
                  value={headerTax}
                  onChange={(event) => setHeaderTax(event.target.value)}
                  className="nx-input"
                />
              </div>
              <div>
                <label htmlFor="header-notes" className="nx-label">
                  Notas
                </label>
                <textarea
                  id="header-notes"
                  rows={2}
                  value={headerNotes}
                  onChange={(event) => setHeaderNotes(event.target.value)}
                  className="nx-input"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setHeaderEditing(false)}
                  className="nx-btn nx-btn-sm nx-btn-secondary"
                  disabled={busy}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => void submitHeader()}
                  className="nx-btn nx-btn-sm nx-btn-primary disabled:opacity-60"
                  disabled={busy}
                >
                  Guardar
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Acciones de estado */}
      {editable && (
        <div className="nx-card flex flex-wrap gap-2 p-4">
          <button
            type="button"
            onClick={() => {
              setActionError(null);
              setConfirmOpen(true);
            }}
            className="nx-btn nx-btn-success"
          >
            <Icon name="check" size={16} />
            Confirmar compra
          </button>
          <button
            type="button"
            onClick={() => {
              setActionError(null);
              setCancelOpen(true);
            }}
            className="nx-btn nx-btn-danger"
          >
            <Icon name="x-circle" size={16} />
            Cancelar compra
          </button>
        </div>
      )}

      {/* Ítems */}
      <div className="nx-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h3 className="text-sm font-semibold text-foreground">
            Productos ({items.length})
          </h3>
          {editable && (
            <button
              type="button"
              onClick={openAddItem}
              className="nx-btn nx-btn-primary"
            >
              <Icon name="plus" size={16} />
              Agregar producto
            </button>
          )}
        </div>
        {!hasItems ? (
          <EmptyState
            title="Sin productos"
            hint="Agregue productos a la compra para poder confirmarla."
            icon="package"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="nx-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th className="text-right">Cantidad</th>
                  <th className="text-right">Costo</th>
                  <th className="hidden text-right sm:table-cell">Descuento</th>
                  <th className="hidden text-right sm:table-cell">Impuesto</th>
                  <th className="text-right">Subtotal</th>
                  <th className="text-right">Total</th>
                  {editable && (
                    <th className="text-right">Acciones</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className="font-medium text-foreground">
                      {item.product_name ?? '—'}
                    </td>
                    <td className="text-right text-foreground">{item.quantity}</td>
                    <td className="text-right text-foreground">
                      {formatCurrency(item.unit_cost)}
                    </td>
                    <td className="hidden text-right text-foreground sm:table-cell">
                      {formatCurrency(item.discount)}
                    </td>
                    <td className="hidden text-right text-foreground sm:table-cell">
                      {formatCurrency(item.tax)}
                    </td>
                    <td className="text-right text-foreground">
                      {formatCurrency(item.subtotal)}
                    </td>
                    <td className="text-right font-medium text-foreground">
                      {formatCurrency(item.total)}
                    </td>
                    {editable && (
                      <td className="whitespace-nowrap text-right">
                        <button
                          type="button"
                          onClick={() => openEditItem(item)}
                          className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                        >
                          <Icon name="pencil" size={14} />
                          Editar
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setActionError(null);
                            setRemovingItem(item);
                          }}
                          className="nx-btn nx-btn-sm nx-btn-ghost text-red-600 dark:text-red-400"
                        >
                          <Icon name="trash" size={14} />
                          Eliminar
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal agregar/editar ítem */}
      <Modal
        open={itemModalOpen}
        title={editingItem ? `Editar producto: ${editingItem.product_name}` : 'Agregar producto'}
        onClose={() => setItemModalOpen(false)}
      >
        <div className="space-y-3">
          {!editingItem && (
            <div>
              <label htmlFor="item-product" className="nx-label">
                Producto *
              </label>
              <select
                id="item-product"
                value={itemForm.productId}
                onChange={(event) => handleProductSelected(event.target.value)}
                className="nx-select"
              >
                <option value="">Seleccione…</option>
                {productsState.data?.items.map((product: ApiProduct) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                    {product.barcode ? ` (${product.barcode})` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="item-quantity" className="nx-label">
                Cantidad *
              </label>
              <input
                id="item-quantity"
                type="number"
                min={1}
                step={1}
                value={itemForm.quantity}
                onChange={(event) => setField('quantity', event.target.value)}
                className="nx-input"
              />
            </div>
            <div>
              <label htmlFor="item-cost" className="nx-label">
                Costo unitario *
              </label>
              <input
                id="item-cost"
                type="number"
                min={0}
                step="0.01"
                value={itemForm.unitCost}
                onChange={(event) => setField('unitCost', event.target.value)}
                className="nx-input"
              />
            </div>
            <div>
              <label htmlFor="item-discount" className="nx-label">
                Descuento
              </label>
              <input
                id="item-discount"
                type="number"
                min={0}
                step="0.01"
                value={itemForm.discount}
                onChange={(event) => setField('discount', event.target.value)}
                className="nx-input"
              />
            </div>
            <div>
              <label htmlFor="item-tax" className="nx-label">
                Impuesto
              </label>
              <input
                id="item-tax"
                type="number"
                min={0}
                step="0.01"
                value={itemForm.tax}
                onChange={(event) => setField('tax', event.target.value)}
                className="nx-input"
              />
            </div>
          </div>
          {itemError && (
            <p className="rounded-md border border-red-300 bg-red-100/60 px-3 py-2 text-sm text-red-800 dark:bg-red-500/10 dark:text-red-300">
              {itemError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setItemModalOpen(false)}
              className="nx-btn nx-btn-secondary"
              disabled={busy}
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => void submitItem()}
              disabled={busy}
              className="nx-btn nx-btn-primary disabled:opacity-60"
            >
              {busy ? 'Guardando…' : editingItem ? 'Guardar cambios' : 'Agregar'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Confirmaciones */}
      <ConfirmDialog
        open={confirmOpen}
        title="Confirmar compra"
        message={
          '¿Confirmar esta compra?\n\nAl confirmar:\n- Se actualizará el inventario.\n- Se registrarán movimientos.\n- La compra ya no podrá editarse.'
        }
        confirmLabel="Confirmar"
        busy={busy}
        onConfirm={async () => {
          if (!id) return;
          const ok = await runAction(() => confirmPurchase(id));
          if (ok) setConfirmOpen(false);
        }}
        onCancel={() => setConfirmOpen(false)}
      />
      <ConfirmDialog
        open={cancelOpen}
        title="Cancelar compra"
        message="¿Cancelar esta compra? Quedará en estado CANCELLED y no podrá confirmarse."
        destructive
        busy={busy}
        onConfirm={async () => {
          if (!id) return;
          const ok = await runAction(() => cancelPurchase(id));
          if (ok) setCancelOpen(false);
        }}
        onCancel={() => setCancelOpen(false)}
      />
      <ConfirmDialog
        open={removingItem !== null}
        title="Eliminar producto"
        message={`¿Eliminar el producto ${
          removingItem?.product_name ?? ''
        } de la compra?`}
        destructive
        busy={busy}
        onConfirm={async () => {
          if (!id || !removingItem) return;
          const ok = await runAction(() =>
            removePurchaseItem(id, removingItem.id),
          );
          if (ok) setRemovingItem(null);
        }}
        onCancel={() => setRemovingItem(null)}
      />
    </div>
  );
}
