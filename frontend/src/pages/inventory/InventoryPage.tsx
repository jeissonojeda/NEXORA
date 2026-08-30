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
import LoadingState from '../../components/ui/LoadingState';
import Pagination from '../../components/ui/Pagination';
import PageHeader from '../../components/ui/PageHeader';
import Icon from '../../components/ui/Icon';
import StockOperationModal, {
  type StockOperationType,
} from '../../components/domain/StockOperationModal';
import { formatDateTime } from '../../utils/format';
import { userHasPermission } from '../../utils/permissions';

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
  const canWrite = userHasPermission(user, 'inventory.update');

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
    <div className="animate-fade-in space-y-5">
      <PageHeader
        title="Inventario"
        subtitle="Existencias, movimientos y alertas de stock."
        actions={
          !canWrite && (
            <p className="text-xs text-muted">
              Solo lectura — requiere permisos de inventario para registrar movimientos.
            </p>
          )
        }
      />

      {/* Pestañas */}
      <div className="border-b border-line">
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
                  ? 'border-[var(--nx-primary)] text-primary'
                  : 'border-transparent text-muted hover:border-line-strong hover:text-foreground'
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
        <section aria-label="Existencias" className="space-y-4">
          <div className="relative max-w-sm">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint">
              <Icon name="search" size={16} />
            </span>
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Buscar producto…"
              className="nx-input pl-9"
            />
          </div>
          <ErrorAlert
            message={stockState.error}
            onRetry={stockState.loading ? undefined : () => void stockState.reload()}
          />
          <div className="nx-card overflow-hidden">
            {stockState.loading ? (
              <div className="p-5">
                <LoadingState rows={5} />
              </div>
            ) : (stockState.data?.total ?? 0) === 0 ? (
              <EmptyState title="Sin productos activos" icon="package" />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="nx-table">
                    <thead>
                      <tr>
                        <th>Producto</th>
                        <th className="text-right">Stock</th>
                        <th className="hidden text-right sm:table-cell">Mínimo</th>
                        <th>Estado</th>
                        {canWrite && (
                          <th className="text-right">Operaciones</th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {stockState.data?.items.map((product) => {
                        const isLow = product.stock <= product.minimum_stock;
                        return (
                          <tr key={product.id}>
                            <td className="font-medium text-foreground">{product.name}</td>
                            <td className={`text-right ${isLow ? 'font-bold text-red-600 dark:text-red-400' : 'text-foreground'}`}>
                              {product.stock}
                            </td>
                            <td className="hidden text-right text-muted sm:table-cell">
                              {product.minimum_stock}
                            </td>
                            <td>
                              {isLow ? (
                                <Badge tone="amber">Reponer</Badge>
                              ) : (
                                <Badge tone="green">OK</Badge>
                              )}
                            </td>
                            {canWrite && (
                              <td className="whitespace-nowrap text-right">
                                <button type="button" onClick={() => openOperation('ENTRY', product)} className="nx-btn nx-btn-sm nx-btn-ghost text-emerald-700 dark:text-emerald-400">Entrada</button>
                                <button type="button" onClick={() => openOperation('EXIT', product)} disabled={product.stock === 0} className="nx-btn nx-btn-sm nx-btn-ghost text-red-600 dark:text-red-400 disabled:opacity-40">Salida</button>
                                <button type="button" onClick={() => openOperation('RETURN', product)} className="nx-btn nx-btn-sm nx-btn-ghost text-primary">Devolución</button>
                                <button type="button" onClick={() => openOperation('ADJUSTMENT', product)} className="nx-btn nx-btn-sm nx-btn-ghost text-amber-700 dark:text-amber-400">Ajuste</button>
                              </td>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <Pagination page={page} pageSize={PAGE_SIZE} total={stockState.data?.total ?? 0} onChange={setPage} />
              </>
            )}
          </div>
        </section>
      )}

      {tab === 'movements' && (
        <section aria-label="Movimientos" className="space-y-4">
          <select
            value={movementTypeFilter}
            onChange={(event) => setMovementTypeFilter(event.target.value)}
            aria-label="Filtrar por tipo de movimiento"
            className="nx-select max-w-xs"
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
          <div className="nx-card overflow-hidden">
            {movementsState.loading ? (
              <div className="p-5">
                <LoadingState rows={5} />
              </div>
            ) : (movementsState.data?.total ?? 0) === 0 ? (
              <EmptyState title="Sin movimientos registrados" hint="Las entradas, salidas, ajustes y devoluciones aparecerán aquí." icon="layers" />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="nx-table">
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Tipo</th>
                        <th className="hidden text-right md:table-cell">Anterior</th>
                        <th className="text-right">Cantidad</th>
                        <th className="hidden text-right sm:table-cell">Nuevo</th>
                        <th className="hidden lg:table-cell">Motivo</th>
                        <th className="hidden sm:table-cell">Usuario</th>
                      </tr>
                    </thead>
                    <tbody>
                      {movementsState.data?.items.map((movement) => (
                        <tr key={movement.id}>
                          <td className="whitespace-nowrap text-muted">{formatDateTime(movement.created_at)}</td>
                          <td><Badge tone={MOVEMENT_TONE[movement.movement_type]}>{movementLabel(movement.movement_type)}</Badge></td>
                          <td className="hidden text-right text-faint md:table-cell">{movement.previous_stock}</td>
                          <td className={`text-right font-medium ${movement.movement_type === 'EXIT' ? 'text-red-600 dark:text-red-400' : 'text-emerald-700 dark:text-emerald-400'}`}>
                            {movement.movement_type === 'EXIT' ? '-' : '+'}{movement.quantity}
                          </td>
                          <td className="hidden text-right font-semibold text-foreground sm:table-cell">{movement.new_stock}</td>
                          <td className="hidden max-w-[200px] truncate text-muted lg:table-cell">{movement.reason || '—'}</td>
                          <td className="hidden text-muted sm:table-cell">{movement.created_by_username ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination page={movementPage} pageSize={PAGE_SIZE} total={movementsState.data?.total ?? 0} onChange={setMovementPage} />
              </>
            )}
          </div>
        </section>
      )}

      {tab === 'low' && (
        <section aria-label="Productos con stock bajo" className="space-y-4">
          <ErrorAlert
            message={lowStockState.error}
            onRetry={lowStockState.loading ? undefined : () => void lowStockState.reload()}
          />
          <div className="nx-card overflow-hidden">
            {lowStockState.loading ? (
              <div className="p-5">
                <LoadingState rows={5} />
              </div>
            ) : (lowStockState.data?.length ?? 0) === 0 ? (
              <EmptyState title="Ningún producto bajo el mínimo" hint="Todo el inventario está por encima del stock mínimo." icon="check-circle" />
            ) : (
              <div className="overflow-x-auto">
                <table className="nx-table">
                  <thead>
                    <tr>
                      <th>Producto</th>
                      <th className="hidden sm:table-cell">Categoría</th>
                      <th className="text-right">Stock</th>
                      <th className="text-right">Mínimo</th>
                      <th>Alerta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lowStockState.data?.map((product) => (
                      <tr key={product.id}>
                        <td className="font-medium text-foreground">{product.name}</td>
                        <td className="hidden text-muted sm:table-cell">{product.category.name}</td>
                        <td className="text-right font-bold text-red-600 dark:text-red-400">{product.stock}</td>
                        <td className="text-right text-muted">{product.minimum_stock}</td>
                        <td>
                          <Badge tone="red">Reponer urgentemente</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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
