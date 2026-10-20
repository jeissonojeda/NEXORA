import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import { cancelPurchase, listPurchases } from '../../services/purchases';
import type { ApiPurchase, PurchaseStatus } from '../../types/purchase';
import { purchaseStatusLabel } from '../../types/purchase';
import { userHasPermission } from '../../utils/permissions';
import { formatCurrency, formatDateTime } from '../../utils/format';
import PurchaseBuilder from '../../components/domain/PurchaseBuilder';
import SuppliersManager from '../../components/domain/SuppliersManager';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import LoadingState from '../../components/ui/LoadingState';
import PageHeader from '../../components/ui/PageHeader';
import Icon from '../../components/ui/Icon';

type Tab = 'registrar' | 'proveedores';

const RECENT_LIMIT = 10;

const STATUS_TONE: Record<PurchaseStatus, 'gray' | 'green' | 'red'> = {
  DRAFT: 'gray',
  CONFIRMED: 'green',
  CANCELLED: 'red',
};

interface ComprasProveedoresPageProps {
  initialTab?: Tab;
}

export default function ComprasProveedoresPage({
  initialTab = 'registrar',
}: ComprasProveedoresPageProps) {
  const { user } = useAuth();
  const canCreatePurchase = userHasPermission(user, 'purchases.create');
  const canCancelPurchase = userHasPermission(user, 'purchases.cancel');
  const canCreateSupplier = userHasPermission(user, 'suppliers.create');

  const [tab, setTab] = useState<Tab>(initialTab);

  const recentState = useAsync(
    () => listPurchases({ limit: RECENT_LIMIT }),
    [],
  );

  const [cancelling, setCancelling] = useState<ApiPurchase | null>(null);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  async function confirmCancel() {
    if (!cancelling) return;
    setCancelBusy(true);
    setCancelError(null);
    try {
      await cancelPurchase(cancelling.id);
      setCancelling(null);
      await recentState.reload();
    } catch (err) {
      setCancelError(extractErrorMessage(err));
    } finally {
      setCancelBusy(false);
    }
  }

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        title="Compras y proveedores"
        subtitle="Registra compras, actualiza inventario y administra tus proveedores."
      />

      {/* Pestañas */}
      <div className="flex gap-1 border-b border-line">
        {(
          [
            ['registrar', 'Registrar compra'],
            ['proveedores', 'Proveedores'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold transition-colors ${
              tab === value
                ? 'border-[var(--nx-primary)] text-primary'
                : 'border-transparent text-muted hover:text-foreground'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'proveedores' ? (
        <SuppliersManager onChanged={() => void recentState.reload()} />
      ) : canCreatePurchase ? (
        <>
          <PurchaseBuilder
            canCreateSupplier={canCreateSupplier}
            onSaved={() => void recentState.reload()}
          />

          {/* Compras recientes */}
          <div className="nx-card overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <h3 className="text-sm font-semibold text-foreground">
                Compras recientes
              </h3>
            </div>
            {recentState.error && <ErrorAlert message={recentState.error} />}
            {recentState.loading ? (
              <div className="p-5">
                <LoadingState rows={4} />
              </div>
            ) : (recentState.data?.items.length ?? 0) === 0 ? (
              <EmptyState
                title="Sin compras"
                hint="Registra tu primera compra con el formulario de arriba."
                icon="cart"
              />
            ) : (
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
                    {recentState.data?.items.map((purchase) => (
                      <tr key={purchase.id}>
                        <td className="font-mono text-xs font-medium text-foreground">
                          {purchase.purchase_number}
                        </td>
                        <td className="text-foreground">
                          {purchase.supplier.name}
                        </td>
                        <td className="hidden text-muted md:table-cell">
                          {formatDateTime(purchase.created_at)}
                        </td>
                        <td>
                          <Badge tone={STATUS_TONE[purchase.status]}>
                            {purchaseStatusLabel(purchase.status)}
                          </Badge>
                        </td>
                        <td className="text-right font-medium tabular-nums text-foreground">
                          {formatCurrency(purchase.total)}
                        </td>
                        <td className="whitespace-nowrap text-right">
                          <Link
                            to={`/purchases/${purchase.id}`}
                            className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                          >
                            <Icon name="eye" size={14} />
                            Abrir
                          </Link>
                          {canCancelPurchase && purchase.status === 'DRAFT' && (
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
            )}
          </div>
        </>
      ) : (
        <div className="nx-card p-6 text-sm text-muted">
          No tienes permiso para registrar compras.
        </div>
      )}

      <ConfirmDialog
        open={cancelling !== null}
        title="Cancelar compra"
        message={`¿Cancelar la compra ${cancelling?.purchase_number ?? ''}? Quedará en estado CANCELLED y no podrá confirmarse.`}
        confirmLabel="Cancelar compra"
        destructive
        busy={cancelBusy}
        error={cancelError}
        onConfirm={() => void confirmCancel()}
        onCancel={() => setCancelling(null)}
      />
    </div>
  );
}
