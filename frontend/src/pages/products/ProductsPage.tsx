import { useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import { listCategories } from '../../services/categories';
import { listSuppliers } from '../../services/suppliers';
import {
  createProduct,
  deactivateProduct,
  getProductByBarcode,
  listProducts,
  updateProduct,
} from '../../services/products';
import type { ApiProduct, ProductFormValues } from '../../types/catalog';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert, { InlineError } from '../../components/ui/ErrorAlert';
import Pagination from '../../components/ui/Pagination';
import Modal from '../../components/ui/Modal';
import ProductForm from '../../components/domain/ProductForm';

const inputClass =
  'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none';

const PAGE_SIZE = 10;

export default function ProductsPage() {
  const { user } = useAuth();
  const canWrite =
    user?.roles.some((role) => ['ADMIN', 'INVENTORY_MANAGER'].includes(role.name)) ??
    false;

  const categoriesState = useAsync(() => listCategories(), []);
  const suppliersState = useAsync(
    () =>
      listSuppliers({ isActive: true, orderBy: 'name', order: 'asc', limit: 100 }),
    [],
  );

  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [supplierId, setSupplierId] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [page, setPage] = useState(1);

  const productsState = useAsync(
    () =>
      listProducts({
        q: query || null,
        categoryId: categoryId || null,
        supplierId: supplierId || null,
        isActive:
          statusFilter === 'all' ? null : statusFilter === 'active',
        lowStock: lowStockOnly,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [query, categoryId, supplierId, statusFilter, lowStockOnly, page],
  );

  // Búsqueda con debounce
  useEffect(() => {
    const timer = setTimeout(() => setQuery(searchInput.trim()), 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  function changeCategory(value: string) {
    setCategoryId(value);
    setPage(1);
  }

  function changeSupplier(value: string) {
    setSupplierId(value);
    setPage(1);
  }

  function changeStatus(value: string) {
    setStatusFilter(value);
    setPage(1);
  }

  function changeLowStockOnly(value: boolean) {
    setLowStockOnly(value);
    setPage(1);
  }

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ApiProduct | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deactivating, setDeactivating] = useState<ApiProduct | null>(null);
  const [deactivateError, setDeactivateError] = useState<string | null>(null);
  const [barcodeLookup, setBarcodeLookup] = useState('');
  const [barcodeResult, setBarcodeResult] = useState<ApiProduct | null>(null);
  const [barcodeError, setBarcodeError] = useState<string | null>(null);
  const [lookupBusy, setLookupBusy] = useState(false);

  async function handleSubmit(values: ProductFormValues & { stock: string }) {
    setBusy(true);
    setFormError(null);
    try {
      if (editing) {
        await updateProduct(editing.id, values);
      } else {
        await createProduct(values);
      }
      setFormOpen(false);
      setEditing(null);
      await productsState.reload();
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
      await deactivateProduct(deactivating.id);
      setDeactivating(null);
      await productsState.reload();
    } catch (err) {
      setDeactivateError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleBarcodeLookup(event: React.FormEvent) {
    event.preventDefault();
    if (!barcodeLookup.trim()) return;
    setLookupBusy(true);
    setBarcodeError(null);
    setBarcodeResult(null);
    try {
      const product = await getProductByBarcode(barcodeLookup);
      setBarcodeResult(product);
    } catch (err) {
      setBarcodeError(
        extractErrorMessage(err).includes('not found') ||
          extractErrorMessage(err).includes('No existe')
          ? `No hay producto activo con código ${barcodeLookup}`
          : extractErrorMessage(err),
      );
    } finally {
      setLookupBusy(false);
    }
  }

  const total = productsState.data?.total ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-gray-900">Productos</h2>
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
            + Nuevo producto
          </button>
        )}
      </div>

      {/* Filtros */}
      <div className="grid grid-cols-1 gap-3 rounded-lg bg-white p-4 shadow sm:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <label htmlFor="filter-search" className="block text-xs font-medium text-gray-500">
            Buscar (nombre o código)
          </label>
          <input
            id="filter-search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Ej. leche o 750123…"
            className={`mt-1 ${inputClass}`}
          />
        </div>
        <div>
          <label htmlFor="filter-category" className="block text-xs font-medium text-gray-500">
            Categoría
          </label>
          <select
            id="filter-category"
            value={categoryId}
            onChange={(event) => changeCategory(event.target.value)}
            className={`mt-1 ${inputClass}`}
          >
            <option value="">Todas</option>
            {categoriesState.data?.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="filter-supplier" className="block text-xs font-medium text-gray-500">
            Proveedor
          </label>
          <select
            id="filter-supplier"
            value={supplierId}
            onChange={(event) => changeSupplier(event.target.value)}
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
          <label htmlFor="filter-status" className="block text-xs font-medium text-gray-500">
            Estado
          </label>
          <select
            id="filter-status"
            value={statusFilter}
            onChange={(event) => changeStatus(event.target.value)}
            className={`mt-1 ${inputClass}`}
          >
            <option value="all">Todos</option>
            <option value="active">Activos</option>
            <option value="inactive">Inactivos</option>
          </select>
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={lowStockOnly}
              onChange={(event) => changeLowStockOnly(event.target.checked)}
              className="rounded border-gray-300"
            />
            Solo stock bajo
          </label>
        </div>
      </div>

      {/* Consulta por código de barras */}
      <form
        onSubmit={(event) => void handleBarcodeLookup(event)}
        className="flex flex-wrap items-start gap-3 rounded-lg bg-white p-4 shadow"
      >
        <div className="min-w-[220px] flex-1">
          <label htmlFor="barcode-lookup" className="block text-xs font-medium text-gray-500">
            Escáner / consulta por código de barras
          </label>
          <input
            id="barcode-lookup"
            value={barcodeLookup}
            onChange={(event) => setBarcodeLookup(event.target.value)}
            placeholder="Escanea o digita el código y presiona Enter"
            autoComplete="off"
            className={`mt-1 ${inputClass}`}
          />
        </div>
        <button
          type="submit"
          disabled={lookupBusy}
          className="mt-5 rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
        >
          {lookupBusy ? 'Buscando…' : 'Consultar'}
        </button>
        {barcodeError && <InlineError message={barcodeError} />}
      </form>

      {barcodeResult && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-900">
          <p className="font-semibold">{barcodeResult.name}</p>
          <p className="mt-1">
            Stock: {barcodeResult.stock} · Precio:{' '}
            {Number(barcodeResult.sale_price).toFixed(2)} · Categoría:{' '}
            {barcodeResult.category.name}
          </p>
        </div>
      )}

      <ErrorAlert
        message={
          productsState.error ??
          barcodeError ??
          categoriesState.error ??
          suppliersState.error ??
          null
        }
        onRetry={
          productsState.loading ? undefined : () => void productsState.reload()
        }
      />

      <div className="overflow-hidden rounded-lg bg-white shadow">
        {productsState.loading ? (
          <p className="px-4 py-10 text-center text-sm text-gray-500">Cargando…</p>
        ) : total === 0 ? (
          <EmptyState title="Sin productos" hint="Ajusta los filtros o crea un producto." />
        ) : (
          <>
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Producto</th>
                  <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">
                    Código
                  </th>
                  <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 sm:table-cell">
                    Categoría
                  </th>
                  <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">
                    Proveedor
                  </th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Precio venta</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Stock</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Estado</th>
                  {canWrite && (
                    <th className="px-4 py-3 text-right font-semibold text-gray-600">Acciones</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {productsState.data?.items.map((product) => {
                  const isLow =
                    product.stock <= product.minimum_stock && product.is_active;
                  return (
                    <tr key={product.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900">{product.name}</p>
                        {product.description && (
                          <p className="max-w-xs truncate text-xs text-gray-400">
                            {product.description}
                          </p>
                        )}
                      </td>
                      <td className="hidden px-4 py-3 font-mono text-xs text-gray-500 md:table-cell">
                        {product.barcode || '—'}
                      </td>
                      <td className="hidden px-4 py-3 text-gray-600 sm:table-cell">
                        {product.category.name}
                      </td>
                      <td className="hidden max-w-[160px] truncate px-4 py-3 text-gray-600 md:table-cell">
                        {product.supplier?.name ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-800">
                        ₡{Number(product.sale_price).toLocaleString('es-CR', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={isLow ? 'font-bold text-red-600' : 'text-gray-800'}>
                          {product.stock}
                        </span>
                        <span className="ml-1 text-xs text-gray-400">/ min {product.minimum_stock}</span>
                      </td>
                      <td className="px-4 py-3">
                        {isLow ? (
                          <Badge tone="amber">Stock bajo</Badge>
                        ) : product.is_active ? (
                          <Badge tone="green">Activo</Badge>
                        ) : (
                          <Badge tone="red">Inactivo</Badge>
                        )}
                      </td>
                      {canWrite && (
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          <button
                            type="button"
                            onClick={() => {
                              setEditing(product);
                              setFormError(null);
                              setFormOpen(true);
                            }}
                            className="mr-2 text-sm font-medium text-blue-600 hover:text-blue-800"
                          >
                            Editar
                          </button>
                          {product.is_active && (
                            <button
                              type="button"
                              onClick={() => {
                                setDeactivateError(null);
                                setDeactivating(product);
                              }}
                              className="text-sm font-medium text-red-600 hover:text-red-800"
                            >
                              Desactivar
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
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
        title={editing ? `Editar producto: ${editing.name}` : 'Nuevo producto'}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
        }}
      >
        <ProductForm
          key={editing?.id ?? 'new'}
          initial={
            editing
              ? {
                  name: editing.name,
                  barcode: editing.barcode ?? '',
                  description: editing.description ?? '',
                  purchase_price: String(Number(editing.purchase_price)),
                  sale_price: String(Number(editing.sale_price)),
                  category_id: editing.category.id,
                  supplier_id: editing.supplier?.id ?? '',
                  minimum_stock: String(editing.minimum_stock),
                }
              : undefined
          }
          categories={categoriesState.data ?? []}
          suppliers={suppliersState.data?.items ?? []}
          isEdit={editing !== null}
          busy={busy}
          error={formError}
          submitLabel={editing ? 'Guardar cambios' : 'Crear producto'}
          onSubmit={(values) => void handleSubmit(values)}
        />
      </Modal>

      <ConfirmDialog
        open={deactivating !== null}
        title="Desactivar producto"
        message={`¿Desactivar "${deactivating?.name}"? El historial de movimientos se conserva.`}
        confirmLabel="Desactivar"
        destructive
        busy={busy}
        error={deactivateError}
        onConfirm={() => void confirmDeactivate()}
        onCancel={() => setDeactivating(null)}
      />
    </div>
  );
}
