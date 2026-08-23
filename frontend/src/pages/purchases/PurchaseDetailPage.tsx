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
import Modal from '../../components/ui/Modal';
import { formatCurrency, formatDateTime } from '../../utils/format';

const inputClass =
  'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none';
const labelClass = 'block text-sm font-medium text-gray-700';

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
    return <p className="py-10 text-center text-sm text-gray-500">Cargando compra…</p>;
  }
  if (!purchase) {
    return (
      <EmptyState
        title="Compra no encontrada"
        hint="La compra solicitada no existe o fue eliminada."
      />
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            to="/purchases"
            className="text-sm font-medium text-blue-600 hover:text-blue-800"
          >
            ← Volver a compras
          </Link>
          <h2 className="mt-1 font-mono text-xl font-bold text-gray-900">
            {purchase.purchase_number}
          </h2>
        </div>
        <Badge tone={STATUS_TONE[purchase.status]}>
          {purchaseStatusLabel(purchase.status)}
        </Badge>
      </div>

      {actionError && <ErrorAlert message={actionError} />}

      {/* Encabezado */}
      <div className="grid grid-cols-1 gap-4 rounded-lg bg-white p-4 shadow md:grid-cols-2">
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-gray-500">Proveedor</dt>
            <dd className="font-medium text-gray-900">{purchase.supplier.name}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-gray-500">Fecha de creación</dt>
            <dd className="text-gray-800">{formatDateTime(purchase.created_at)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-gray-500">Creada por</dt>
            <dd className="text-gray-800">{purchase.created_by_username ?? '—'}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-gray-500">Confirmada</dt>
            <dd className="text-gray-800">
              {purchase.confirmed_at ? formatDateTime(purchase.confirmed_at) : '—'}
            </dd>
          </div>
          {!headerEditing && (
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Notas</dt>
              <dd className="max-w-[60%] text-right text-gray-800">
                {purchase.notes || '—'}
              </dd>
            </div>
          )}
        </dl>

        {/* Totales */}
        <div className="rounded-md bg-gray-50 p-4 text-sm">
          <div className="flex justify-between py-1">
            <span className="text-gray-500">Subtotal</span>
            <span className="font-medium text-gray-900">
              {formatCurrency(purchase.subtotal)}
            </span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-gray-500">Descuento</span>
            <span className="text-gray-900">
              −{formatCurrency(purchase.discount)}
            </span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-gray-500">Impuesto</span>
            <span className="text-gray-900">+{formatCurrency(purchase.tax)}</span>
          </div>
          <div className="mt-2 flex justify-between border-t border-gray-200 pt-2">
            <span className="font-semibold text-gray-700">Total</span>
            <span className="text-lg font-bold text-gray-900">
              {formatCurrency(purchase.total)}
            </span>
          </div>
          {editable && !headerEditing && (
            <button
              type="button"
              onClick={openHeaderEdit}
              className="mt-3 text-xs font-medium text-blue-600 hover:text-blue-800"
            >
              Editar descuento / impuesto / notas
            </button>
          )}
          {headerEditing && (
            <div className="mt-3 space-y-2">
              <div>
                <label htmlFor="header-discount" className={labelClass}>
                  Descuento
                </label>
                <input
                  id="header-discount"
                  value={headerDiscount}
                  onChange={(event) => setHeaderDiscount(event.target.value)}
                  className={`mt-1 ${inputClass}`}
                />
              </div>
              <div>
                <label htmlFor="header-tax" className={labelClass}>
                  Impuesto
                </label>
                <input
                  id="header-tax"
                  value={headerTax}
                  onChange={(event) => setHeaderTax(event.target.value)}
                  className={`mt-1 ${inputClass}`}
                />
              </div>
              <div>
                <label htmlFor="header-notes" className={labelClass}>
                  Notas
                </label>
                <textarea
                  id="header-notes"
                  rows={2}
                  value={headerNotes}
                  onChange={(event) => setHeaderNotes(event.target.value)}
                  className={`mt-1 ${inputClass}`}
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setHeaderEditing(false)}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                  disabled={busy}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => void submitHeader()}
                  className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
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
        <div className="flex flex-wrap gap-2 rounded-lg bg-white p-4 shadow">
          <button
            type="button"
            onClick={() => {
              setActionError(null);
              setConfirmOpen(true);
            }}
            className="rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700"
          >
            Confirmar compra
          </button>
          <button
            type="button"
            onClick={() => {
              setActionError(null);
              setCancelOpen(true);
            }}
            className="rounded-md border border-red-300 px-4 py-2 text-sm font-semibold text-red-600 hover:bg-red-50"
          >
            Cancelar compra
          </button>
        </div>
      )}

      {/* Ítems */}
      <div className="overflow-hidden rounded-lg bg-white shadow">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h3 className="text-sm font-semibold text-gray-900">
            Productos ({items.length})
          </h3>
          {editable && (
            <button
              type="button"
              onClick={openAddItem}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
            >
              + Agregar producto
            </button>
          )}
        </div>
        {!hasItems ? (
          <EmptyState
            title="Sin productos"
            hint="Agregue productos a la compra para poder confirmarla."
          />
        ) : (
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Producto</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Cantidad</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Costo</th>
                <th className="hidden px-4 py-3 text-right font-semibold text-gray-600 sm:table-cell">
                  Descuento
                </th>
                <th className="hidden px-4 py-3 text-right font-semibold text-gray-600 sm:table-cell">
                  Impuesto
                </th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Subtotal</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Total</th>
                {editable && (
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">
                    Acciones
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {item.product_name ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-800">{item.quantity}</td>
                  <td className="px-4 py-3 text-right text-gray-800">
                    {formatCurrency(item.unit_cost)}
                  </td>
                  <td className="hidden px-4 py-3 text-right text-gray-800 sm:table-cell">
                    {formatCurrency(item.discount)}
                  </td>
                  <td className="hidden px-4 py-3 text-right text-gray-800 sm:table-cell">
                    {formatCurrency(item.tax)}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-800">
                    {formatCurrency(item.subtotal)}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-gray-900">
                    {formatCurrency(item.total)}
                  </td>
                  {editable && (
                    <td className="whitespace-nowrap px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => openEditItem(item)}
                        className="mr-2 text-sm font-medium text-blue-600 hover:text-blue-800"
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setActionError(null);
                          setRemovingItem(item);
                        }}
                        className="text-sm font-medium text-red-600 hover:text-red-800"
                      >
                        Eliminar
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
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
              <label htmlFor="item-product" className={labelClass}>
                Producto *
              </label>
              <select
                id="item-product"
                value={itemForm.productId}
                onChange={(event) => handleProductSelected(event.target.value)}
                className={`mt-1 ${inputClass}`}
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
              <label htmlFor="item-quantity" className={labelClass}>
                Cantidad *
              </label>
              <input
                id="item-quantity"
                type="number"
                min={1}
                step={1}
                value={itemForm.quantity}
                onChange={(event) => setField('quantity', event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </div>
            <div>
              <label htmlFor="item-cost" className={labelClass}>
                Costo unitario *
              </label>
              <input
                id="item-cost"
                type="number"
                min={0}
                step="0.01"
                value={itemForm.unitCost}
                onChange={(event) => setField('unitCost', event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </div>
            <div>
              <label htmlFor="item-discount" className={labelClass}>
                Descuento
              </label>
              <input
                id="item-discount"
                type="number"
                min={0}
                step="0.01"
                value={itemForm.discount}
                onChange={(event) => setField('discount', event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </div>
            <div>
              <label htmlFor="item-tax" className={labelClass}>
                Impuesto
              </label>
              <input
                id="item-tax"
                type="number"
                min={0}
                step="0.01"
                value={itemForm.tax}
                onChange={(event) => setField('tax', event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </div>
          </div>
          {itemError && (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {itemError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setItemModalOpen(false)}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              disabled={busy}
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => void submitItem()}
              disabled={busy}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
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
