import { useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import {
  listLowStock,
  listMovements,
  registerAdjustment,
  registerEntry,
  registerExit,
  registerReturn,
} from '../../services/inventory';
import { listProducts } from '../../services/products';
import type { ApiProduct, Movement } from '../../types/catalog';
import { movementLabel } from '../../types/catalog';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import Pagination from '../../components/ui/Pagination';
import StockOperationModal, {
  type StockOperationType,
} from '../../components/domain/StockOperationModal';
import { formatDateTime } from '../../utils/format';

type Tab = 'stock' | 'movements' | 'low';

const TABS: { id: Tab; label: string }[] = [
  { id: 'stock', label: 'Existencias' },
  { id: 'movements', label: 'Movimientos' },
  { id: 'low', label: 'Stock bajo' },
];

const MOVEMENT_TONE: Record<Movement['movement_type'], 'green' | 'red' | 'amber' | 'blue'> = {
  ENTRY: 'green',
  EXIT: 'red',
  ADJUSTMENT: 'amber',
  RETURN: 'blue',
};

const PAGE_SIZE = 10;

export default function InventoryPage() {
  const { user } = useAuth();
  const canWrite =
    user?.roles.some((role) => ['ADMIN', 'INVENTORY_MANAGER'].includes(role.name)) ??
    false;

  const [tab, setTab] = useState<Tab>('stock');

  // Existencias
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);

  const stockState = useAsync(
    () =>
      listProducts({
        q: query || null,
        isActive: true,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [query, page],
  );
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Movimientos
  const [movementPage, setMovementPage] = useState(1);
  const [movementTypeFilter, setMovementTypeFilter] = useState('');
  const movementsState = useAsync(
    () =>
      listMovements({
        movementType: movementTypeFilter || null,
        skip: (movementPage - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [movementTypeFilter, movementPage],
  );

  // Stock bajo
  const lowStockState = useAsync(() => listLowStock(), []);

  // Operaciones
  const [operation, setOperation] = useState<StockOperationType | null>(null);
  const [operationProduct, setOperationProduct] = useState<ApiProduct | null>(null);
  const [opBusy, setOpBusy] = useState(false);
  const [opError, setOpError] = useState<string | null>(null);

  function openOperation(type: StockOperationType, product: ApiProduct) {
    setOpError(null);
    setOperationProduct(product);
    setOperation(type);
  }

  async function submitEntryExitReturn(
    quantity: number,
    reason: string,
    referenceId: string,
  ) {
    if (!operation || !operationProduct) return;
    setOpBusy(true);
    setOpError(null);
    try {
      if (operation === 'ENTRY') {
        await registerEntry({ product_id: operationProduct.id, quantity, reason, reference_id: referenceId });
      } else if (operation === 'EXIT') {
        await registerExit({ product_id: operationProduct.id, quantity, reason, reference_id: referenceId });
      } else if (operation === 'RETURN') {
        await registerReturn({ product_id: operationProduct.id, quantity, reason, reference_id: referenceId });
      }
      closeOperation();
      await Promise.all([stockState.reload(), movementsState.reload(), lowStockState.reload()]);
    } catch (err) {
      setOpError(extractErrorMessage(err));
    } finally {
      setOpBusy(false);
    }
  }

  async function submitAdjustment(newStock: number, reason: string) {
    if (!operationProduct) return;
    setOpBusy(true);
    setOpError(null);
    try {
      await registerAdjustment({ product_id: operationProduct.id, new_stock: newStock, reason });
      closeOperation();
      await Promise.all([stockState.reload(), movementsState.reload(), lowStockState.reload()]);
    } catch (err) {
      setOpError(extractErrorMessage(err));
    } finally {
      setOpBusy(false);
    }
  }

  function closeOperation() {
    setOperation(null);
    setOperationProduct(null);
    setOpError(null);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-gray-900">Inventario</h2>
        {!canWrite && (
          <p className="text-xs text-gray-500">
            Solo lectura — requiere permisos de inventario para registrar movimientos.
          </p>
        )}
      </div>

      {/* Pestañas */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-4" aria-label="Secciones de inventario">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setTab(item.id);
                if (item.id === 'movements') setMovementPage(1);
                if (item.id === 'stock') setPage(1);
              }}
              className={`whitespace-nowrap border-b-2 px-1 py-2 text-sm font-medium ${
                tab === item.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
              }`}
            >
              {item.label}
              {item.id === 'movements' && movementsState.data
                ? ` (${movementsState.data.total})`
                : ''}
              {item.id === 'low' && lowStockState.data && lowStockState.data.length > 0
                ? ` (${lowStockState.data.length})`
                : ''}
            </button>
          ))}
        </nav>
      </div>

      {tab === 'stock' && (
        <section aria-label="Existencias" className="space-y-3">
          <input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Buscar producto…"
            className="block w-full max-w-sm rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <ErrorAlert
            message={stockState.error}
            onRetry={stockState.loading ? undefined : () => void stockState.reload()}
          />
          <div className="overflow-hidden rounded-lg bg-white shadow">
            {stockState.loading ? (
              <p className="px-4 py-10 text-center text-sm text-gray-500">Cargando…</p>
            ) : (stockState.data?.total ?? 0) === 0 ? (
              <EmptyState title="Sin productos activos" />
            ) : (
              <>
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left font-semibold text-gray-600">Producto</th>
                      <th className="px-4 py-3 text-right font-semibold text-gray-600">Stock</th>
                      <th className="hidden px-4 py-3 text-right font-semibold text-gray-600 sm:table-cell">Mínimo</th>
                      <th className="px-4 py-3 text-left font-semibold text-gray-600">Estado</th>
                      {canWrite && (
                        <th className="px-4 py-3 text-right font-semibold text-gray-600">Operaciones</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {stockState.data?.items.map((product) => {
                      const isLow = product.stock <= product.minimum_stock;
                      return (
                        <tr key={product.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 font-medium text-gray-900">{product.name}</td>
                          <td className={`px-4 py-3 text-right ${isLow ? 'font-bold text-red-600' : 'text-gray-800'}`}>
                            {product.stock}
                          </td>
                          <td className="hidden px-4 py-3 text-right text-gray-500 sm:table-cell">
                            {product.minimum_stock}
                          </td>
                          <td className="px-4 py-3">
                            {isLow ? (
                              <Badge tone="amber">Reponer</Badge>
                            ) : (
                              <Badge tone="green">OK</Badge>
                            )}
                          </td>
                          {canWrite && (
                            <td className="px-4 py-3 text-right whitespace-nowrap">
                              <button type="button" onClick={() => openOperation('ENTRY', product)} className="mr-2 rounded bg-green-600 px-2 py-1 text-xs font-semibold text-white hover:bg-green-700">Entrada</button>
                              <button type="button" onClick={() => openOperation('EXIT', product)} disabled={product.stock === 0} className="mr-2 rounded bg-red-600 px-2 py-1 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-40">Salida</button>
                              <button type="button" onClick={() => openOperation('RETURN', product)} className="mr-2 rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700">Devolución</button>
                              <button type="button" onClick={() => openOperation('ADJUSTMENT', product)} className="rounded bg-amber-600 px-2 py-1 text-xs font-semibold text-white hover:bg-amber-700">Ajuste</button>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <Pagination page={page} pageSize={PAGE_SIZE} total={stockState.data?.total ?? 0} onChange={setPage} />
              </>
            )}
          </div>
        </section>
      )}

      {tab === 'movements' && (
        <section aria-label="Movimientos" className="space-y-3">
          <select
            value={movementTypeFilter}
            onChange={(event) => setMovementTypeFilter(event.target.value)}
            aria-label="Filtrar por tipo de movimiento"
            className="block w-full max-w-xs rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="">Todos los tipos</option>
            <option value="ENTRY">Entradas</option>
            <option value="EXIT">Salidas</option>
            <option value="ADJUSTMENT">Ajustes</option>
            <option value="RETURN">Devoluciones</option>
          </select>
          <ErrorAlert
            message={movementsState.error}
            onRetry={movementsState.loading ? undefined : () => void movementsState.reload()}
          />
          <div className="overflow-hidden rounded-lg bg-white shadow">
            {movementsState.loading ? (
              <p className="px-4 py-10 text-center text-sm text-gray-500">Cargando…</p>
            ) : (movementsState.data?.total ?? 0) === 0 ? (
              <EmptyState title="Sin movimientos registrados" hint="Las entradas, salidas, ajustes y devoluciones aparecerán aquí." />
            ) : (
              <>
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left font-semibold text-gray-600">Fecha</th>
                      <th className="px-4 py-3 text-left font-semibold text-gray-600">Tipo</th>
                      <th className="hidden px-4 py-3 text-right font-semibold text-gray-600 md:table-cell">Anterior</th>
                      <th className="px-4 py-3 text-right font-semibold text-gray-600">Cantidad</th>
                      <th className="hidden px-4 py-3 text-right font-semibold text-gray-600 sm:table-cell">Nuevo</th>
                      <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 lg:table-cell">Motivo</th>
                      <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 sm:table-cell">Usuario</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {movementsState.data?.items.map((movement) => (
                      <tr key={movement.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 whitespace-nowrap text-gray-600">{formatDateTime(movement.created_at)}</td>
                        <td className="px-4 py-3"><Badge tone={MOVEMENT_TONE[movement.movement_type]}>{movementLabel(movement.movement_type)}</Badge></td>
                        <td className="hidden px-4 py-3 text-right text-gray-400 md:table-cell">{movement.previous_stock}</td>
                        <td className={`px-4 py-3 text-right font-medium ${movement.movement_type === 'EXIT' ? 'text-red-600' : 'text-green-700'}`}>
                          {movement.movement_type === 'EXIT' ? '-' : '+'}{movement.quantity}
                        </td>
                        <td className="hidden px-4 py-3 text-right font-semibold text-gray-800 sm:table-cell">{movement.new_stock}</td>
                        <td className="hidden max-w-[200px] truncate px-4 py-3 text-gray-500 lg:table-cell">{movement.reason || '—'}</td>
                        <td className="hidden px-4 py-3 text-gray-500 sm:table-cell">{movement.created_by_username ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <Pagination page={movementPage} pageSize={PAGE_SIZE} total={movementsState.data?.total ?? 0} onChange={setMovementPage} />
              </>
            )}
          </div>
        </section>
      )}

      {tab === 'low' && (
        <section aria-label="Productos con stock bajo" className="space-y-3">
          <ErrorAlert
            message={lowStockState.error}
            onRetry={lowStockState.loading ? undefined : () => void lowStockState.reload()}
          />
          <div className="overflow-hidden rounded-lg bg-white shadow">
            {lowStockState.loading ? (
              <p className="px-4 py-10 text-center text-sm text-gray-500">Cargando…</p>
            ) : (lowStockState.data?.length ?? 0) === 0 ? (
              <EmptyState title="Ningún producto bajo el mínimo" hint="Todo el inventario está por encima del stock mínimo." />
            ) : (
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-amber-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-gray-600">Producto</th>
                    <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 sm:table-cell">Categoría</th>
                    <th className="px-4 py-3 text-right font-semibold text-gray-600">Stock</th>
                    <th className="px-4 py-3 text-right font-semibold text-gray-600">Mínimo</th>
                    <th className="px-4 py-3 text-left font-semibold text-gray-600">Alerta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {lowStockState.data?.map((product) => (
                    <tr key={product.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-900">{product.name}</td>
                      <td className="hidden px-4 py-3 text-gray-500 sm:table-cell">{product.category.name}</td>
                      <td className="px-4 py-3 text-right font-bold text-red-600">{product.stock}</td>
                      <td className="px-4 py-3 text-right text-gray-600">{product.minimum_stock}</td>
                      <td className="px-4 py-3">
                        <Badge tone="red">⚠ Reponer urgentemente</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      <StockOperationModal
        operation={operation}
        product={operationProduct}
        busy={opBusy}
        error={opError}
        onClose={closeOperation}
        onSubmitEntryExitReturn={(quantity, reason, referenceId) =>
          void submitEntryExitReturn(quantity, reason, referenceId)
        }
        onSubmitAdjustment={(newStock, reason) =>
          void submitAdjustment(newStock, reason)
        }
      />
    </div>
  );
}

