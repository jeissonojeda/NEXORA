import { useMemo, useState } from 'react';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import { createSupplier, listSuppliers } from '../../services/suppliers';
import { listProducts } from '../../services/products';
import { confirmPurchase, createPurchase } from '../../services/purchases';
import type { ApiProduct } from '../../types/catalog';
import type { PurchaseItemPayload } from '../../types/purchase';
import { formatCurrency } from '../../utils/format';
import { InlineError } from '../ui/ErrorAlert';
import Icon from '../ui/Icon';

interface BuilderLine {
  key: string;
  productId: string;
  productName: string;
  quantity: string;
  unitCost: string;
  discount: string;
  tax: string;
}

const EMPTY_LINE = {
  productId: '',
  quantity: '1',
  unitCost: '',
  discount: '0',
  tax: '0',
};

interface PurchaseBuilderProps {
  canCreateSupplier: boolean;
  onSaved: () => void;
  onOpenPurchase?: (purchaseId: string) => void;
}

function number(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export default function PurchaseBuilder({
  canCreateSupplier,
  onSaved,
  onOpenPurchase,
}: PurchaseBuilderProps) {
  const suppliersState = useAsync(
    () => listSuppliers({ isActive: true, orderBy: 'name', order: 'asc', limit: 200 }),
    [],
  );
  const productsState = useAsync(
    () => listProducts({ isActive: true, limit: 200 }),
    [],
  );

  const [supplierId, setSupplierId] = useState('');
  const [notes, setNotes] = useState('');
  const [headerDiscount, setHeaderDiscount] = useState('0');
  const [headerTax, setHeaderTax] = useState('0');

  const [supplierCreatorOpen, setSupplierCreatorOpen] = useState(false);
  const [newSupplierName, setNewSupplierName] = useState('');
  const [newSupplierPhone, setNewSupplierPhone] = useState('');
  const [newSupplierIdentification, setNewSupplierIdentification] = useState('');
  const [supplierCreatorBusy, setSupplierCreatorBusy] = useState(false);
  const [supplierCreatorError, setSupplierCreatorError] = useState<string | null>(
    null,
  );

  const [productQuery, setProductQuery] = useState('');
  const [lineForm, setLineForm] = useState({ ...EMPTY_LINE });
  const [lines, setLines] = useState<BuilderLine[]>([]);
  const [lineError, setLineError] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const filteredProducts = useMemo(() => {
    const products = productsState.data?.items ?? [];
    const query = productQuery.trim().toLowerCase();
    if (!query) return products;
    return products.filter(
      (product) =>
        product.name.toLowerCase().includes(query) ||
        (product.barcode ?? '').toLowerCase().includes(query),
    );
  }, [productsState.data, productQuery]);

  const subtotal = lines.reduce(
    (acc, line) => acc + number(line.quantity) * number(line.unitCost),
    0,
  );
  const total = subtotal - number(headerDiscount) + number(headerTax);

  function resetLineForm() {
    setLineForm({ ...EMPTY_LINE });
    setProductQuery('');
    setLineError(null);
  }

  function lineTotal(line: BuilderLine): number {
    return (
      number(line.quantity) * number(line.unitCost) -
      number(line.discount) +
      number(line.tax)
    );
  }

  function handleProductSelected(productId: string) {
    const product = productsState.data?.items.find(
      (candidate: ApiProduct) => candidate.id === productId,
    );
    setLineForm((prev) => ({
      ...prev,
      productId,
      unitCost: product ? String(Number(product.purchase_price)) : prev.unitCost,
    }));
  }

  function addLine() {
    setLineError(null);
    if (!lineForm.productId) {
      setLineError('Selecciona un producto');
      return;
    }
    if (lines.some((line) => line.productId === lineForm.productId)) {
      setLineError('El producto ya está en la compra');
      return;
    }
    const quantity = Number(lineForm.quantity);
    if (!Number.isInteger(quantity) || quantity <= 0) {
      setLineError('La cantidad debe ser un entero mayor que cero');
      return;
    }
    for (const [label, value] of [
      ['costo unitario', lineForm.unitCost],
      ['descuento', lineForm.discount || '0'],
      ['impuesto', lineForm.tax || '0'],
    ] as const) {
      if (Number.isNaN(Number(value)) || Number(value) < 0) {
        setLineError(`El ${label} debe ser un número ≥ 0`);
        return;
      }
    }
    const product = productsState.data?.items.find(
      (candidate) => candidate.id === lineForm.productId,
    );
    setLines((prev) => [
      ...prev,
      {
        key: `${lineForm.productId}-${Date.now()}`,
        productId: lineForm.productId,
        productName: product?.name ?? 'Producto',
        quantity: lineForm.quantity,
        unitCost: lineForm.unitCost,
        discount: lineForm.discount,
        tax: lineForm.tax,
      },
    ]);
    resetLineForm();
  }

  function updateLine(key: string, field: keyof BuilderLine, value: string) {
    setLines((prev) =>
      prev.map((line) => (line.key === key ? { ...line, [field]: value } : line)),
    );
  }

  function removeLine(key: string) {
    setLines((prev) => prev.filter((line) => line.key !== key));
  }

  async function createSupplierInline() {
    if (!newSupplierName.trim()) {
      setSupplierCreatorError('El nombre es obligatorio');
      return;
    }
    setSupplierCreatorBusy(true);
    setSupplierCreatorError(null);
    try {
      const created = await createSupplier({
        name: newSupplierName.trim(),
        identification: newSupplierIdentification,
        contact_name: '',
        phone: newSupplierPhone,
        email: '',
        address: '',
        city: '',
        notes: '',
      });
      await suppliersState.reload();
      setSupplierId(created.id);
      setNewSupplierName('');
      setNewSupplierPhone('');
      setNewSupplierIdentification('');
      setSupplierCreatorOpen(false);
    } catch (err) {
      setSupplierCreatorError(extractErrorMessage(err));
    } finally {
      setSupplierCreatorBusy(false);
    }
  }

  function buildItems(): PurchaseItemPayload[] | string {
    if (!supplierId) return 'Selecciona un proveedor';
    if (lines.length === 0) return 'Agrega al menos un producto';
    const items: PurchaseItemPayload[] = [];
    for (const line of lines) {
      const quantity = Number(line.quantity);
      const unitCost = number(line.unitCost);
      const discount = number(line.discount);
      const tax = number(line.tax);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        return `Cantidad inválida en "${line.productName}"`;
      }
      if (unitCost < 0 || discount < 0 || tax < 0) {
        return `Valores negativos en "${line.productName}"`;
      }
      if (discount > quantity * unitCost) {
        return `El descuento excede el subtotal en "${line.productName}"`;
      }
      items.push({
        product_id: line.productId,
        quantity,
        unit_cost: unitCost,
        discount,
        tax,
      });
    }
    return items;
  }

  async function save(confirm: boolean) {
    const items = buildItems();
    if (typeof items === 'string') {
      setError(items);
      return;
    }
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const purchase = await createPurchase({
        supplier_id: supplierId,
        notes: notes.trim() || null,
        discount: number(headerDiscount),
        tax: number(headerTax),
        items,
      });
      if (confirm) {
        try {
          await confirmPurchase(purchase.id);
          setSuccess(
            `Compra ${purchase.purchase_number} registrada y confirmada. El inventario fue actualizado.`,
          );
        } catch (err) {
          setSuccess(
            `Compra ${purchase.purchase_number} guardada como borrador.`,
          );
          setError(`No se pudo confirmar: ${extractErrorMessage(err)}`);
        }
      } else {
        setSuccess(`Compra ${purchase.purchase_number} guardada como borrador.`);
      }
      setSupplierId('');
      setNotes('');
      setHeaderDiscount('0');
      setHeaderTax('0');
      setLines([]);
      resetLineForm();
      onSaved();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      {success && (
        <div
          role="status"
          className="flex items-center justify-between gap-3 rounded-lg border border-emerald-300 bg-emerald-100/60 px-4 py-2.5 text-sm text-emerald-900 dark:bg-emerald-500/10 dark:text-emerald-200"
        >
          <span className="flex items-center gap-2">
            <Icon name="check" size={16} />
            {success}
          </span>
          <button
            type="button"
            onClick={() => setSuccess(null)}
            className="text-xs font-semibold hover:underline"
          >
            Cerrar
          </button>
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-300 bg-red-100/60 px-4 py-2.5 text-sm text-red-800 dark:bg-red-500/10 dark:text-red-300"
        >
          {error}
        </div>
      )}

      {/* Proveedor */}
      <div className="nx-card p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-bold uppercase tracking-widest text-faint">
            Proveedor
          </h3>
          {canCreateSupplier && !supplierCreatorOpen && (
            <button
              type="button"
              onClick={() => {
                setSupplierCreatorError(null);
                setSupplierCreatorOpen(true);
              }}
              className="text-xs font-semibold text-primary hover:brightness-75"
            >
              + Registrar proveedor
            </button>
          )}
        </div>
        <select
          value={supplierId}
          onChange={(event) => setSupplierId(event.target.value)}
          className="nx-select"
          aria-label="Proveedor de la compra"
        >
          <option value="">Selecciona un proveedor…</option>
          {suppliersState.data?.items.map((supplier) => (
            <option key={supplier.id} value={supplier.id}>
              {supplier.name}
            </option>
          ))}
        </select>
        {supplierCreatorOpen && (
          <div className="mt-3 space-y-2 rounded-lg border border-line bg-surface-2 p-3">
            <input
              value={newSupplierName}
              onChange={(event) => setNewSupplierName(event.target.value)}
              className="nx-input"
              placeholder="Nombre del proveedor *"
              aria-label="Nombre del nuevo proveedor"
            />
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <input
                value={newSupplierPhone}
                onChange={(event) => setNewSupplierPhone(event.target.value)}
                className="nx-input"
                placeholder="Teléfono (opcional)"
                aria-label="Teléfono del nuevo proveedor"
              />
              <input
                value={newSupplierIdentification}
                onChange={(event) =>
                  setNewSupplierIdentification(event.target.value)
                }
                className="nx-input"
                placeholder="Identificación (opcional)"
                aria-label="Identificación del nuevo proveedor"
              />
            </div>
            <InlineError message={supplierCreatorError ?? undefined} />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="nx-btn nx-btn-sm nx-btn-secondary"
                onClick={() => setSupplierCreatorOpen(false)}
                disabled={supplierCreatorBusy}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="nx-btn nx-btn-sm nx-btn-primary"
                onClick={() => void createSupplierInline()}
                disabled={supplierCreatorBusy}
              >
                {supplierCreatorBusy ? 'Registrando…' : 'Registrar proveedor'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Agregar productos */}
      <div className="nx-card p-5">
        <h3 className="mb-3 text-sm font-bold uppercase tracking-widest text-faint">
          Agregar producto
        </h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <label htmlFor="pb-product-search" className="nx-label">
              Buscar producto
            </label>
            <input
              id="pb-product-search"
              value={productQuery}
              onChange={(event) => setProductQuery(event.target.value)}
              className="nx-input"
              placeholder="Nombre o código…"
            />
          </div>
          <div className="lg:col-span-4">
            <label htmlFor="pb-product" className="nx-label">
              Producto <span className="text-red-500">*</span>
            </label>
            <select
              id="pb-product"
              value={lineForm.productId}
              onChange={(event) => handleProductSelected(event.target.value)}
              className="nx-select"
            >
              <option value="">Seleccionar…</option>
              {filteredProducts.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name}
                  {product.barcode ? ` (${product.barcode})` : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="lg:col-span-1">
            <label htmlFor="pb-qty" className="nx-label">
              Cant.
            </label>
            <input
              id="pb-qty"
              type="number"
              min={1}
              step={1}
              value={lineForm.quantity}
              onChange={(event) =>
                setLineForm((prev) => ({ ...prev, quantity: event.target.value }))
              }
              className="nx-input"
            />
          </div>
          <div className="lg:col-span-1">
            <label htmlFor="pb-cost" className="nx-label">
              Costo
            </label>
            <input
              id="pb-cost"
              type="number"
              min={0}
              step="0.01"
              value={lineForm.unitCost}
              onChange={(event) =>
                setLineForm((prev) => ({ ...prev, unitCost: event.target.value }))
              }
              className="nx-input"
            />
          </div>
          <div className="lg:col-span-1">
            <label htmlFor="pb-discount" className="nx-label">
              Desc.
            </label>
            <input
              id="pb-discount"
              type="number"
              min={0}
              step="0.01"
              value={lineForm.discount}
              onChange={(event) =>
                setLineForm((prev) => ({ ...prev, discount: event.target.value }))
              }
              className="nx-input"
            />
          </div>
          <div className="lg:col-span-1">
            <label htmlFor="pb-tax" className="nx-label">
              Imp.
            </label>
            <input
              id="pb-tax"
              type="number"
              min={0}
              step="0.01"
              value={lineForm.tax}
              onChange={(event) =>
                setLineForm((prev) => ({ ...prev, tax: event.target.value }))
              }
              className="nx-input"
            />
          </div>
          <div className="flex items-end lg:col-span-1">
            <button
              type="button"
              onClick={addLine}
              className="nx-btn nx-btn-secondary w-full"
            >
              <Icon name="plus" size={16} />
            </button>
          </div>
        </div>
        <InlineError message={lineError ?? undefined} />
      </div>

      {/* Líneas */}
      <div className="nx-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h3 className="text-sm font-semibold text-foreground">
            Productos ({lines.length})
          </h3>
        </div>
        {lines.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-muted">
            Aún no has agregado productos a la compra.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="nx-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th className="text-right">Cantidad</th>
                  <th className="text-right">Costo</th>
                  <th className="text-right">Descuento</th>
                  <th className="text-right">Impuesto</th>
                  <th className="text-right">Total</th>
                  <th className="text-right">Quitar</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => (
                  <tr key={line.key}>
                    <td className="font-medium text-foreground">{line.productName}</td>
                    <td className="text-right">
                      <input
                        type="number"
                        min={1}
                        step={1}
                        value={line.quantity}
                        onChange={(event) =>
                          updateLine(line.key, 'quantity', event.target.value)
                        }
                        className="nx-input w-20 text-right"
                        aria-label={`Cantidad de ${line.productName}`}
                      />
                    </td>
                    <td className="text-right">
                      <input
                        type="number"
                        min={0}
                        step="0.01"
                        value={line.unitCost}
                        onChange={(event) =>
                          updateLine(line.key, 'unitCost', event.target.value)
                        }
                        className="nx-input w-24 text-right"
                        aria-label={`Costo de ${line.productName}`}
                      />
                    </td>
                    <td className="text-right">
                      <input
                        type="number"
                        min={0}
                        step="0.01"
                        value={line.discount}
                        onChange={(event) =>
                          updateLine(line.key, 'discount', event.target.value)
                        }
                        className="nx-input w-20 text-right"
                        aria-label={`Descuento de ${line.productName}`}
                      />
                    </td>
                    <td className="text-right">
                      <input
                        type="number"
                        min={0}
                        step="0.01"
                        value={line.tax}
                        onChange={(event) =>
                          updateLine(line.key, 'tax', event.target.value)
                        }
                        className="nx-input w-20 text-right"
                        aria-label={`Impuesto de ${line.productName}`}
                      />
                    </td>
                    <td className="text-right font-medium tabular-nums text-foreground">
                      {formatCurrency(lineTotal(line))}
                    </td>
                    <td className="text-right">
                      <button
                        type="button"
                        onClick={() => removeLine(line.key)}
                        className="nx-btn nx-btn-sm nx-btn-ghost text-red-600 dark:text-red-400"
                        aria-label={`Quitar ${line.productName}`}
                      >
                        <Icon name="trash" size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Totales y acciones */}
      <div className="nx-card grid grid-cols-1 gap-4 p-5 md:grid-cols-2">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="pb-discount-header" className="nx-label">
                Descuento general
              </label>
              <input
                id="pb-discount-header"
                type="number"
                min={0}
                step="0.01"
                value={headerDiscount}
                onChange={(event) => setHeaderDiscount(event.target.value)}
                className="nx-input"
              />
            </div>
            <div>
              <label htmlFor="pb-tax-header" className="nx-label">
                Impuesto general
              </label>
              <input
                id="pb-tax-header"
                type="number"
                min={0}
                step="0.01"
                value={headerTax}
                onChange={(event) => setHeaderTax(event.target.value)}
                className="nx-input"
              />
            </div>
          </div>
          <div>
            <label htmlFor="pb-notes" className="nx-label">
              Notas
            </label>
            <textarea
              id="pb-notes"
              rows={2}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="nx-input"
            />
          </div>
        </div>
        <div className="flex flex-col justify-between rounded-xl bg-surface-2 p-4">
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-muted">Subtotal</span>
              <span className="font-medium tabular-nums text-foreground">
                {formatCurrency(subtotal)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Descuento</span>
              <span className="tabular-nums text-foreground">
                −{formatCurrency(number(headerDiscount))}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Impuesto</span>
              <span className="tabular-nums text-foreground">
                +{formatCurrency(number(headerTax))}
              </span>
            </div>
            <div className="flex justify-between border-t border-line pt-1">
              <span className="font-semibold text-foreground">Total</span>
              <span className="text-lg font-bold tabular-nums text-foreground">
                {formatCurrency(total)}
              </span>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={() => void save(false)}
              disabled={busy}
              className="nx-btn nx-btn-secondary disabled:opacity-60"
            >
              {busy ? 'Guardando…' : 'Guardar borrador'}
            </button>
            <button
              type="button"
              onClick={() => void save(true)}
              disabled={busy}
              className="nx-btn nx-btn-primary disabled:opacity-60"
            >
              <Icon name="check" size={16} />
              {busy ? 'Procesando…' : 'Registrar y confirmar compra'}
            </button>
          </div>
          {onOpenPurchase && (
            <p className="mt-2 text-right text-xs text-faint">
              Al confirmar se actualiza el inventario de forma atómica.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
