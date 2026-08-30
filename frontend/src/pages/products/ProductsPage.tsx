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
import { formatCurrency } from '../../utils/format';
import { userHasPermission } from '../../utils/permissions';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert, { InlineError } from '../../components/ui/ErrorAlert';
import LoadingState from '../../components/ui/LoadingState';
import Pagination from '../../components/ui/Pagination';
import Modal from '../../components/ui/Modal';
import PageHeader from '../../components/ui/PageHeader';
import Icon from '../../components/ui/Icon';
import ProductForm from '../../components/domain/ProductForm';

const PAGE_SIZE = 10;

export default function ProductsPage() {
  const { user } = useAuth();
  const canWrite =
    userHasPermission(user, 'products.create') ||
    userHasPermission(user, 'products.update');

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
      const message = extractErrorMessage(err);
      setBarcodeError(
        message.includes('not found') || message.includes('No existe')
          ? `No hay producto activo con código ${barcodeLookup}`
          : message,
      );
    } finally {
      setLookupBusy(false);
    }
  }

  const total = productsState.data?.total ?? 0;

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        title="Productos"
        subtitle="Catálogo, códigos de barras y precios."
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
              Nuevo producto
            </button>
          )
        }
      />

      {/* Filtros */}
      <div className="nx-card grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <label htmlFor="filter-search" className="nx-label">
            Buscar (nombre o código)
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint">
              <Icon name="search" size={16} />
            </span>
            <input
              id="filter-search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Ej. leche o 750123…"
              className="nx-input pl-9"
            />
          </div>
        </div>
        <div>
          <label htmlFor="filter-category" className="nx-label">
            Categoría
          </label>
          <select
            id="filter-category"
            value={categoryId}
            onChange={(event) => changeCategory(event.target.value)}
            className="nx-select"
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
          <label htmlFor="filter-supplier" className="nx-label">
            Proveedor
          </label>
          <select
            id="filter-supplier"
            value={supplierId}
            onChange={(event) => changeSupplier(event.target.value)}
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
          <label htmlFor="filter-status" className="nx-label">
            Estado
          </label>
          <select
            id="filter-status"
            value={statusFilter}
            onChange={(event) => changeStatus(event.target.value)}
            className="nx-select"
          >
            <option value="all">Todos</option>
            <option value="active">Activos</option>
            <option value="inactive">Inactivos</option>
          </select>
        </div>
        <div className="flex items-end pb-1">
          <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-muted">
            <input
              type="checkbox"
              checked={lowStockOnly}
              onChange={(event) => changeLowStockOnly(event.target.checked)}
              className="h-4 w-4 rounded border-line-strong accent-[var(--nx-primary)]"
            />
            Solo stock bajo
          </label>
        </div>
      </div>

      {/* Consulta por código de barras */}
      <form
        onSubmit={(event) => void handleBarcodeLookup(event)}
        className="nx-card flex flex-wrap items-start gap-3 p-4"
      >
        <div className="min-w-[220px] flex-1">
          <label htmlFor="barcode-lookup" className="nx-label">
            Escáner / consulta por código de barras
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint">
              <Icon name="scan" size={16} />
            </span>
            <input
              id="barcode-lookup"
              value={barcodeLookup}
              onChange={(event) => setBarcodeLookup(event.target.value)}
              placeholder="Escanea o digita el código y presiona Enter"
              autoComplete="off"
              className="nx-input pl-9"
            />
          </div>
        </div>
        <button type="submit" disabled={lookupBusy} className="nx-btn nx-btn-secondary">
          <Icon name="scan" size={16} />
          {lookupBusy ? 'Buscando…' : 'Consultar'}
        </button>
        {barcodeError && <InlineError message={barcodeError} />}
      </form>

      {barcodeResult && (
        <div className="nx-card flex items-center gap-3 border-emerald-300 bg-emerald-100/50 p-4 text-sm dark:bg-emerald-500/10 dark:text-emerald-200">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
            <Icon name="check" size={20} />
          </span>
          <div>
            <p className="font-semibold text-emerald-900 dark:text-emerald-200">
              {barcodeResult.name}
            </p>
            <p className="text-emerald-800 dark:text-emerald-300">
              Stock: {barcodeResult.stock} · Precio:{' '}
              {formatCurrency(barcodeResult.sale_price)} · Categoría:{' '}
              {barcodeResult.category.name}
            </p>
          </div>
        </div>
      )}

      <ErrorAlert
        message={
          productsState.error ??
          categoriesState.error ??
          suppliersState.error ??
          null
        }
        onRetry={
          productsState.loading ? undefined : () => void productsState.reload()
        }
      />

      <div className="nx-card overflow-hidden">
        {productsState.loading ? (
          <div className="p-5">
            <LoadingState rows={6} />
          </div>
        ) : total === 0 ? (
          <EmptyState
            title="Sin productos"
            hint="Ajusta los filtros o crea un producto."
            icon="package"
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="nx-table">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th className="hidden md:table-cell">Código</th>
                    <th className="hidden sm:table-cell">Categoría</th>
                    <th className="hidden md:table-cell">Proveedor</th>
                    <th className="text-right">Precio venta</th>
                    <th className="text-right">Stock</th>
                    <th>Estado</th>
                    {canWrite && <th className="text-right">Acciones</th>}
                  </tr>
                </thead>
                <tbody>
                  {productsState.data?.items.map((product) => {
                    const isLow =
                      product.stock <= product.minimum_stock && product.is_active;
                    return (
                      <tr key={product.id}>
                        <td>
                          <p className="font-medium text-foreground">{product.name}</p>
                          {product.description && (
                            <p className="max-w-xs truncate text-xs text-faint">
                              {product.description}
                            </p>
                          )}
                        </td>
                        <td className="hidden font-mono text-xs text-muted md:table-cell">
                          {product.barcode || '—'}
                        </td>
                        <td className="hidden text-muted sm:table-cell">
                          {product.category.name}
                        </td>
                        <td className="hidden max-w-[160px] truncate text-muted md:table-cell">
                          {product.supplier?.name ?? '—'}
                        </td>
                        <td className="text-right font-medium text-foreground">
                          {formatCurrency(product.sale_price)}
                        </td>
                        <td className="text-right">
                          <span
                            className={isLow ? 'font-bold text-red-600 dark:text-red-400' : 'text-foreground'}
                          >
                            {product.stock}
                          </span>
                          <span className="ml-1 text-xs text-faint">
                            / min {product.minimum_stock}
                          </span>
                        </td>
                        <td>
                          {isLow ? (
                            <Badge tone="amber">Stock bajo</Badge>
                          ) : product.is_active ? (
                            <Badge tone="green">Activo</Badge>
                          ) : (
                            <Badge tone="red">Inactivo</Badge>
                          )}
                        </td>
                        {canWrite && (
                          <td className="whitespace-nowrap text-right">
                            <button
                              type="button"
                              onClick={() => {
                                setEditing(product);
                                setFormError(null);
                                setFormOpen(true);
                              }}
                              className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                            >
                              <Icon name="pencil" size={14} />
                              Editar
                            </button>
                            {product.is_active && (
                              <button
                                type="button"
                                onClick={() => {
                                  setDeactivateError(null);
                                  setDeactivating(product);
                                }}
                                className="nx-btn nx-btn-sm nx-btn-ghost text-red-600 dark:text-red-400"
                              >
                                <Icon name="trash" size={14} />
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