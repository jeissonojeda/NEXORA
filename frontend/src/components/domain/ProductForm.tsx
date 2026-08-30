import { useState } from 'react';
import { InlineError } from '../ui/ErrorAlert';
import type {
  ApiCategory,
  ApiSupplierBrief,
  ProductFormValues,
} from '../../types/catalog';

interface ProductFormProps {
  initial?: Partial<ProductFormValues>;
  categories: ApiCategory[];
  suppliers?: ApiSupplierBrief[];
  isEdit: boolean;
  busy: boolean;
  error: string | null;
  submitLabel: string;
  onSubmit: (values: ProductFormValues & { stock: string }) => void;
}

export default function ProductForm({
  initial,
  categories,
  suppliers = [],
  isEdit,
  busy,
  error,
  submitLabel,
  onSubmit,
}: ProductFormProps) {
  const [values, setValues] = useState<ProductFormValues & { stock: string }>({
    name: initial?.name ?? '',
    barcode: initial?.barcode ?? '',
    description: initial?.description ?? '',
    purchase_price: initial?.purchase_price ?? '',
    sale_price: initial?.sale_price ?? '',
    category_id: initial?.category_id ?? '',
    supplier_id: initial?.supplier_id ?? '',
    minimum_stock: initial?.minimum_stock ?? '0',
    stock: '0',
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [supplierQuery, setSupplierQuery] = useState('');

  const filteredSuppliers = supplierQuery.trim()
    ? suppliers.filter((supplier) =>
        supplier.name.toLowerCase().includes(supplierQuery.trim().toLowerCase()),
      )
    : suppliers;

  function set<K extends keyof (ProductFormValues & { stock: string })>(
    field: K,
    value: string,
  ) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!values.name.trim()) errors.name = 'El nombre es obligatorio';
    if (!values.category_id) errors.category_id = 'Selecciona una categoría';
    if (isEdit === false && values.purchase_price.trim()) {
      if (
        Number.isNaN(Number(values.purchase_price)) ||
        Number(values.purchase_price) < 0
      ) {
        errors.purchase_price = 'Debe ser un número ≥ 0';
      }
    }
    if (values.sale_price.trim()) {
      if (
        Number.isNaN(Number(values.sale_price)) ||
        Number(values.sale_price) < 0
      ) {
        errors.sale_price = 'Debe ser un número ≥ 0';
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
    onSubmit(values);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
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
          <label htmlFor="product-category" className="nx-label">
            Categoría <span className="text-red-500">*</span>
          </label>
          <select
            id="product-category"
            value={values.category_id}
            onChange={(event) => set('category_id', event.target.value)}
            className="nx-select"
          >
            <option value="">Seleccionar…</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
          <InlineError message={fieldErrors.category_id} />
        </div>

        <div>
          <label htmlFor="product-supplier" className="nx-label">
            Proveedor
          </label>
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
        </div>

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
            disabled={isEdit}
          />
          <InlineError message={fieldErrors.purchase_price} />
        </div>
        <div>
          <label htmlFor="product-sale" className="nx-label">
            Precio de venta
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
        </div>

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

      <div>
        <label htmlFor="product-description" className="nx-label">
          Descripción
        </label>
        <textarea
          id="product-description"
          rows={2}
          value={values.description}
          onChange={(event) => set('description', event.target.value)}
          className="nx-textarea"
        />
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-red-300 bg-red-100/60 px-3 py-2 text-sm text-red-800 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <button type="submit" disabled={busy} className="nx-btn nx-btn-primary">
          {busy ? 'Guardando…' : submitLabel}
        </button>
      </div>
    </form>
  );
}