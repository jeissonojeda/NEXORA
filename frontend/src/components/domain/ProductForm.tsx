import { useMemo, useState } from 'react';
import { extractErrorMessage } from '../../hooks/useAsync';
import { InlineError } from '../ui/ErrorAlert';
import { formatCurrency } from '../../utils/format';
import type {
  ApiCategory,
  ApiSupplierBrief,
  CategoryFormValues,
  ProductFormValues,
  SupplierFormValues,
} from '../../types/catalog';
import type { ApiTax } from '../../types/settings';

/**
 * Redondeo HALF_UP a 2 decimales, equivalente al ROUND_HALF_UP del backend.
 * Evita diferencias de un centavo entre la vista previa y lo guardado.
 */
function roundHalfUp(value: number, decimals = 2): number {
  const factor = 10 ** decimals;
  const scaled = value * factor;
  return Math.round(scaled + Number.EPSILON * Math.abs(scaled)) / factor;
}

interface ProductFormProps {  initial?: Partial<ProductFormValues>;
  categories: ApiCategory[];
  suppliers?: ApiSupplierBrief[];
  taxes?: ApiTax[];
  isEdit: boolean;
  busy: boolean;
  error: string | null;
  submitLabel: string;
  onSubmit: (values: ProductFormValues & { stock: string }) => void;
  onCancel?: () => void;
  /** Permite crear una categoría sin salir del formulario. */
  onCreateCategory?: (values: CategoryFormValues) => Promise<ApiCategory>;
  /** Permite registrar un proveedor sin salir del formulario. */
  onCreateSupplier?: (values: SupplierFormValues) => Promise<ApiSupplierBrief>;
}

export default function ProductForm({
  initial,
  categories,
  suppliers = [],
  taxes = [],
  isEdit,
  busy,
  error,
  submitLabel,
  onSubmit,
  onCancel,
  onCreateCategory,
  onCreateSupplier,
}: ProductFormProps) {
  const [values, setValues] = useState<ProductFormValues & { stock: string }>({
    name: initial?.name ?? '',
    barcode: initial?.barcode ?? '',
    description: initial?.description ?? '',
    purchase_price: initial?.purchase_price ?? '',
    sale_price: initial?.sale_price ?? '',
    profit_percent: initial?.profit_percent ?? '',
    unit: initial?.unit ?? '',
    category_id: initial?.category_id ?? '',
    supplier_id: initial?.supplier_id ?? '',
    tax_id: initial?.tax_id ?? '',
    minimum_stock: initial?.minimum_stock ?? '0',
    stock: '0',
  });
  const [priceMode, setPriceMode] = useState<'profit' | 'manual'>(
    initial?.sale_price ? 'manual' : 'profit',
  );
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [supplierQuery, setSupplierQuery] = useState('');

  // Categorías/proveedores creados en línea durante esta sesión del formulario.
  const [localCategories, setLocalCategories] = useState<ApiCategory[]>([]);
  const [localSuppliers, setLocalSuppliers] = useState<ApiSupplierBrief[]>([]);

  // Mini-formulario de categoría
  const [categoryCreatorOpen, setCategoryCreatorOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [categoryCreatorError, setCategoryCreatorError] = useState<string | null>(
    null,
  );
  const [categoryCreatorBusy, setCategoryCreatorBusy] = useState(false);

  // Mini-formulario de proveedor
  const [supplierCreatorOpen, setSupplierCreatorOpen] = useState(false);
  const [newSupplierName, setNewSupplierName] = useState('');
  const [newSupplierPhone, setNewSupplierPhone] = useState('');
  const [newSupplierId, setNewSupplierIdentification] = useState('');
  const [supplierCreatorError, setSupplierCreatorError] = useState<string | null>(
    null,
  );
  const [supplierCreatorBusy, setSupplierCreatorBusy] = useState(false);

  const allCategories = [...categories, ...localCategories];
  const allSuppliers = [...suppliers, ...localSuppliers];

  const filteredSuppliers = supplierQuery.trim()
    ? allSuppliers.filter((supplier) =>
        supplier.name.toLowerCase().includes(supplierQuery.trim().toLowerCase()),
      )
    : allSuppliers;

  function set<K extends keyof (ProductFormValues & { stock: string })>(
    field: K,
    value: string,
  ) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  const computedSalePrice = useMemo(() => {
    if (priceMode === 'manual') {
      if (!values.sale_price.trim()) return null;
      const n = Number(values.sale_price);
      return Number.isNaN(n) || n < 0 ? null : roundHalfUp(n);
    }
    const purchase = Number(values.purchase_price) || 0;
    const profit = Number(values.profit_percent) || 0;
    if (purchase < 0 || profit < 0) return null;
    const sale = purchase * (1 + profit / 100);
    return roundHalfUp(sale);
  }, [priceMode, values.purchase_price, values.profit_percent, values.sale_price]);

  const manualProfitPercent = useMemo(() => {
    const purchase = Number(values.purchase_price);
    const sale = Number(values.sale_price);
    if (
      !Number.isFinite(purchase) ||
      !Number.isFinite(sale) ||
      purchase <= 0 ||
      sale < 0
    ) {
      return null;
    }
    return roundHalfUp(((sale - purchase) / purchase) * 100);
  }, [values.purchase_price, values.sale_price]);

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!values.name.trim()) errors.name = 'El nombre es obligatorio';
    if (!values.category_id) errors.category_id = 'Selecciona una categoría';
    if (values.purchase_price.trim()) {
      if (
        Number.isNaN(Number(values.purchase_price)) ||
        Number(values.purchase_price) < 0
      ) {
        errors.purchase_price = 'Debe ser un número ≥ 0';
      }
    }
    if (priceMode === 'profit') {
      if (values.profit_percent.trim()) {
        const p = Number(values.profit_percent);
        if (Number.isNaN(p) || p < 0) {
          errors.profit_percent = 'Debe ser un número ≥ 0';
        }
      }
      if (computedSalePrice === null) {
        errors.sale_price_preview = 'El precio de venta no puede calcularse';
      }
    } else {
      if (!values.sale_price.trim()) {
        errors.sale_price = 'El precio de venta es obligatorio';
      } else {
        const s = Number(values.sale_price);
        if (Number.isNaN(s) || s < 0) {
          errors.sale_price = 'Debe ser un número ≥ 0';
        }
      }
    }
    if (values.minimum_stock.trim()) {
      const min = Number(values.minimum_stock);
      if (!Number.isInteger(min) || min < 0) {
        errors.minimum_stock = 'Debe ser un entero ≥ 0';
      }
    }
    if (!isEdit && values.stock.trim()) {
      const stock = Number(values.stock);
      if (!Number.isInteger(stock) || stock < 0) {
        errors.stock = 'Debe ser un entero ≥ 0';
      }
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!validate()) return;
    const payload: ProductFormValues & { stock: string } = { ...values };
    if (priceMode === 'profit') {
      payload.sale_price = '';
      if (payload.profit_percent.trim() === '') payload.profit_percent = '0';
    } else {
      payload.profit_percent = '';
    }
    onSubmit(payload);
  }

  async function submitNewCategory() {
    if (!onCreateCategory) return;
    if (!newCategoryName.trim()) {
      setCategoryCreatorError('El nombre es obligatorio');
      return;
    }
    setCategoryCreatorBusy(true);
    setCategoryCreatorError(null);
    try {
      const created = await onCreateCategory({
        name: newCategoryName.trim(),
        description: '',
        tax_id: '',
      });
      setLocalCategories((prev) => [...prev, created]);
      set('category_id', created.id);
      setNewCategoryName('');
      setCategoryCreatorOpen(false);
    } catch (err) {
      setCategoryCreatorError(extractErrorMessage(err));
    } finally {
      setCategoryCreatorBusy(false);
    }
  }

  async function submitNewSupplier() {
    if (!onCreateSupplier) return;
    if (!newSupplierName.trim()) {
      setSupplierCreatorError('El nombre es obligatorio');
      return;
    }
    setSupplierCreatorBusy(true);
    setSupplierCreatorError(null);
    try {
      const created = await onCreateSupplier({
        name: newSupplierName.trim(),
        identification: newSupplierId.trim(),
        contact_name: '',
        phone: newSupplierPhone.trim(),
        email: '',
        address: '',
        city: '',
        notes: '',
      });
      setLocalSuppliers((prev) => [...prev, { id: created.id, name: created.name }]);
      set('supplier_id', created.id);
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

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <section className="space-y-4">
        <p className="text-xs font-bold uppercase tracking-widest text-faint">
          Datos generales
        </p>
        <div>
          <label htmlFor="product-name" className="nx-label">
            Nombre <span className="text-red-500">*</span>
          </label>
          <input
            id="product-name"
            value={values.name}
            onChange={(event) => set('name', event.target.value)}
            className="nx-input"
            placeholder="Ej. Leche Entera 1L"
          />
          <InlineError message={fieldErrors.name} />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="product-barcode" className="nx-label">
              Código de barras
            </label>
            <input
              id="product-barcode"
              value={values.barcode}
              onChange={(event) => set('barcode', event.target.value)}
              className="nx-input"
              placeholder="EAN-13 (opcional)"
            />
            <InlineError message={fieldErrors.barcode} />
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="product-category" className="nx-label">
                Categoría <span className="text-red-500">*</span>
              </label>
              {onCreateCategory && !categoryCreatorOpen && (
                <button
                  type="button"
                  onClick={() => {
                    setCategoryCreatorError(null);
                    setCategoryCreatorOpen(true);
                  }}
                  className="text-xs font-semibold text-primary hover:brightness-75"
                >
                  + Nueva categoría
                </button>
              )}
            </div>
            <select
              id="product-category"
              value={values.category_id}
              onChange={(event) => set('category_id', event.target.value)}
              className="nx-select"
            >
              <option value="">Seleccionar…</option>
              {allCategories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
            <InlineError message={fieldErrors.category_id} />
            {categoryCreatorOpen && (
              <div className="mt-2 space-y-2 rounded-lg border border-line bg-surface-2 p-3">
                <input
                  value={newCategoryName}
                  onChange={(event) => setNewCategoryName(event.target.value)}
                  className="nx-input"
                  placeholder="Nombre de la nueva categoría"
                  aria-label="Nombre de la nueva categoría"
                />
                <InlineError message={categoryCreatorError ?? undefined} />
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    className="nx-btn nx-btn-sm nx-btn-secondary"
                    onClick={() => setCategoryCreatorOpen(false)}
                    disabled={categoryCreatorBusy}
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    className="nx-btn nx-btn-sm nx-btn-primary"
                    onClick={() => void submitNewCategory()}
                    disabled={categoryCreatorBusy}
                  >
                    {categoryCreatorBusy ? 'Creando…' : 'Crear categoría'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <label htmlFor="product-supplier" className="nx-label">
              Proveedor
            </label>
            {onCreateSupplier && !supplierCreatorOpen && (
              <button
                type="button"
                onClick={() => {
                  setSupplierCreatorError(null);
                  setSupplierCreatorOpen(true);
                }}
                className="text-xs font-semibold text-primary hover:brightness-75"
              >
                + Nuevo proveedor
              </button>
            )}
          </div>
          <input
            id="supplier-search"
            value={supplierQuery}
            onChange={(event) => setSupplierQuery(event.target.value)}
            className="nx-input"
            placeholder="Filtrar proveedores…"
            aria-label="Buscar proveedor"
          />
          <select
            aria-label="Seleccionar proveedor"
            value={values.supplier_id}
            onChange={(event) => set('supplier_id', event.target.value)}
            className="nx-select mt-2"
          >
            <option value="">Sin proveedor</option>
            {filteredSuppliers.map((supplier) => (
              <option key={supplier.id} value={supplier.id}>
                {supplier.name}
              </option>
            ))}
          </select>
          <InlineError message={fieldErrors.supplier_id} />
          {supplierCreatorOpen && (
            <div className="mt-2 space-y-2 rounded-lg border border-line bg-surface-2 p-3">
              <input
                value={newSupplierName}
                onChange={(event) => setNewSupplierName(event.target.value)}
                className="nx-input"
                placeholder="Nombre del proveedor *"
                aria-label="Nombre del proveedor"
              />
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <input
                  value={newSupplierPhone}
                  onChange={(event) => setNewSupplierPhone(event.target.value)}
                  className="nx-input"
                  placeholder="Teléfono (opcional)"
                  aria-label="Teléfono del proveedor"
                />
                <input
                  value={newSupplierId}
                  onChange={(event) =>
                    setNewSupplierIdentification(event.target.value)
                  }
                  className="nx-input"
                  placeholder="Identificación (opcional)"
                  aria-label="Identificación del proveedor"
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
                  onClick={() => void submitNewSupplier()}
                  disabled={supplierCreatorBusy}
                >
                  {supplierCreatorBusy ? 'Creando…' : 'Crear proveedor'}
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="product-tax" className="nx-label">
              Impuesto (override)
            </label>
            <select
              id="product-tax"
              value={values.tax_id}
              onChange={(event) => set('tax_id', event.target.value)}
              className="nx-select"
            >
              <option value="">Heredar de categoría</option>
              {taxes.map((tax) => (
                <option key={tax.id} value={tax.id}>
                  {tax.name} ({tax.rate}%)
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="product-unit" className="nx-label">
              Unidad
            </label>
            <input
              id="product-unit"
              value={values.unit}
              onChange={(event) => set('unit', event.target.value)}
              className="nx-input"
              placeholder="kg, unidad, caja..."
            />
          </div>
        </div>
      </section>

      <section className="space-y-4 border-t border-line pt-5">
        <p className="text-xs font-bold uppercase tracking-widest text-faint">
          Precios e inventario
        </p>
        <div className="flex gap-2 text-xs">
          <button
            type="button"
            onClick={() => setPriceMode('profit')}
            className={`nx-chip ${priceMode === 'profit' ? 'bg-primary/15 text-primary' : ''}`}
          >
            Por utilidad (% sobre costo)
          </button>
          <button
            type="button"
            onClick={() => setPriceMode('manual')}
            className={`nx-chip ${priceMode === 'manual' ? 'bg-primary/15 text-primary' : ''}`}
          >
            Precio manual
          </button>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="product-purchase" className="nx-label">
              Precio de compra
            </label>
            <input
              id="product-purchase"
              type="number"
              step="0.01"
              min="0"
              value={values.purchase_price}
              onChange={(event) => set('purchase_price', event.target.value)}
              className="nx-input"
            />
            <InlineError message={fieldErrors.purchase_price} />
          </div>
          {priceMode === 'profit' ? (
            <div>
              <label htmlFor="product-profit" className="nx-label">
                Utilidad sobre costo (%)
              </label>
              <input
                id="product-profit"
                type="number"
                step="0.01"
                min="0"
                value={values.profit_percent}
                onChange={(event) => set('profit_percent', event.target.value)}
                className="nx-input"
              />
              <InlineError message={fieldErrors.profit_percent} />
              <p className="mt-1 text-xs text-faint">
                Precio de venta calculado:{' '}
                {computedSalePrice !== null ? formatCurrency(computedSalePrice) : '—'}
              </p>
              <InlineError message={fieldErrors.sale_price_preview} />
            </div>
          ) : (
            <div>
              <label htmlFor="product-sale" className="nx-label">
                Precio de venta <span className="text-red-500">*</span>
              </label>
              <input
                id="product-sale"
                type="number"
                step="0.01"
                min="0"
                value={values.sale_price}
                onChange={(event) => set('sale_price', event.target.value)}
                className="nx-input"
              />
              <InlineError message={fieldErrors.sale_price} />
              <p className="mt-1 text-xs text-faint">
                Utilidad resultante:{' '}
                {manualProfitPercent !== null
                  ? `${manualProfitPercent.toFixed(2)}% sobre el costo`
                  : '—'}
              </p>
            </div>
          )}

          {!isEdit && (
            <div>
              <label htmlFor="product-stock" className="nx-label">
                Stock inicial
              </label>
              <input
                id="product-stock"
                type="number"
                step="1"
                min="0"
                value={values.stock}
                onChange={(event) => set('stock', event.target.value)}
                className="nx-input"
              />
              <InlineError message={fieldErrors.stock} />
            </div>
          )}
          <div>
            <label htmlFor="product-minimum" className="nx-label">
              Stock mínimo
            </label>
            <input
              id="product-minimum"
              type="number"
              step="1"
              min="0"
              value={values.minimum_stock}
              onChange={(event) => set('minimum_stock', event.target.value)}
              className="nx-input"
            />
            <InlineError message={fieldErrors.minimum_stock} />
          </div>
        </div>
      </section>

      <section className="space-y-4 border-t border-line pt-5">
        <p className="text-xs font-bold uppercase tracking-widest text-faint">
          Descripción
        </p>
        <textarea
          id="product-description"
          rows={2}
          value={values.description}
          onChange={(event) => set('description', event.target.value)}
          className="nx-textarea"
        />
      </section>

      {error && (
        <p role="alert" className="rounded-lg border border-red-300 bg-red-100/60 px-3 py-2 text-sm text-red-800 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="nx-btn nx-btn-secondary"
          >
            Cancelar
          </button>
        )}
        <button type="submit" disabled={busy} className="nx-btn nx-btn-primary">
          {busy ? 'Guardando…' : submitLabel}
        </button>
      </div>
    </form>
  );
}
