import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import { cancelSale, confirmSale, getSale } from '../../services/sales';
import type { SaleStatus } from '../../types/sale';
import {
  salePaymentMethodLabel,
  saleStatusLabel,
} from '../../types/sale';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import ErrorAlert from '../../components/ui/ErrorAlert';
import { formatCurrency, formatDateTime } from '../../utils/format';

const STATUS_TONE: Record<SaleStatus, 'gray' | 'green' | 'red'> = {
  DRAFT: 'gray',
  CONFIRMED: 'green',
  CANCELLED: 'red',
};

export default function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const canSell =
    user?.roles.some((role) => ['ADMIN', 'CASHIER'].includes(role.name)) ??
    false;

  const saleState = useAsync(
    () => getSale(id as string),
    [id],
  );

  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  async function handleConfirm() {
    if (!id) return;
    setBusy(true);
    setActionError(null);
    try {
      await confirmSale(id);
      await saleState.reload();
      setConfirming(false);
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    if (!id) return;
    setBusy(true);
    setActionError(null);
    try {
      await cancelSale(id);
      await saleState.reload();
      setCancelling(false);
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (saleState.loading && !saleState.data) {
    return (
      <p className="py-10 text-center text-sm text-muted">Cargando venta…</p>
    );
  }
  if (saleState.error || !saleState.data) {
    return <ErrorAlert message={saleState.error ?? 'Venta no encontrada'} />;
  }

  const sale = saleState.data;
  const isDraft = sale.status === 'DRAFT';

  return (
    <div className="mx-auto max-w-3xl animate-fade-in space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/ventas"
          className="text-sm font-medium text-primary hover:underline"
        >
          ← Volver a ventas
        </Link>
        {canSell && isDraft && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setActionError(null);
                setConfirming(true);
              }}
              className="nx-btn nx-btn-primary"
            >
              Confirmar (cobrar)
            </button>
            <button
              type="button"
              onClick={() => {
                setActionError(null);
                setCancelling(true);
              }}
              className="nx-btn nx-btn-danger"
            >
              Cancelar venta
            </button>
          </div>
        )}
      </div>

      {actionError && <ErrorAlert message={actionError} />}

      {/* Comprobante */}
      <div className="nx-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
          <div>
            <p className="font-mono text-lg font-bold text-foreground">
              {sale.sale_number}
            </p>
            <p className="mt-1 text-xs text-muted">
              {formatDateTime(sale.created_at)} · Cajero:{' '}
              {sale.created_by_username ?? '—'}
            </p>
          </div>
          <Badge tone={STATUS_TONE[sale.status]}>
            {saleStatusLabel(sale.status)}
          </Badge>
        </div>

        <dl className="grid grid-cols-1 gap-3 py-4 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs font-medium uppercase text-muted">Cliente</dt>
            <dd className="mt-0.5 text-foreground">
              {sale.customer?.name ?? 'Consumidor final'}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-muted">Método de pago</dt>
            <dd className="mt-0.5 text-foreground">
              {salePaymentMethodLabel(sale.payment_method)}
            </dd>
          </div>
          {(sale.payment_method === 'CASH' ||
            Number(sale.change_due) > 0) && (
            <div>
              <dt className="text-xs font-medium uppercase text-muted">
                Efectivo / Vuelto
              </dt>
              <dd className="mt-0.5 text-foreground">
                {formatCurrency(sale.amount_paid)}
                {Number(sale.change_due) > 0 &&
                  ` / ${formatCurrency(sale.change_due)}`}
              </dd>
            </div>
          )}
        </dl>

        <div className="overflow-x-auto">
        <table className="nx-table">
          <thead>
            <tr>
              <th className="text-left">Producto</th>
              <th className="text-right">Cant.</th>
              <th className="text-right">Precio</th>
              <th className="text-right">Importe</th>
            </tr>
          </thead>
          <tbody>
            {sale.items.map((item) => (
              <tr key={item.id}>
                <td className="text-foreground">{item.product_name ?? '—'}</td>
                <td className="text-right text-muted">{item.quantity}</td>
                <td className="text-right text-muted">
                  {formatCurrency(item.unit_price)}
                </td>
                <td className="text-right font-medium text-foreground">
                  {formatCurrency(item.subtotal)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>

        <div className="ml-auto mt-4 max-w-xs space-y-1 text-sm">
          <div className="flex justify-between text-muted">
            <span>Subtotal</span>
            <span className="tabular-nums">{formatCurrency(sale.subtotal)}</span>
          </div>
          <div className="flex justify-between text-red-600 dark:text-red-400">
            <span>Descuento</span>
            <span className="tabular-nums">−{formatCurrency(sale.discount)}</span>
          </div>
          <div className="flex justify-between text-muted">
            <span>Impuesto</span>
            <span className="tabular-nums">+{formatCurrency(sale.tax)}</span>
          </div>
          <div className="flex justify-between border-t border-line pt-2 text-base font-bold text-foreground">
            <span>Total</span>
            <span className="tabular-nums">{formatCurrency(sale.total)}</span>
          </div>
        </div>

        {sale.notes && (
          <p className="mt-4 rounded-lg bg-surface px-3 py-2 text-xs text-muted">
            Notas: {sale.notes}
          </p>
        )}
        {sale.confirmed_at && (
          <p className="mt-3 text-right text-xs text-faint">
            Confirmada el {formatDateTime(sale.confirmed_at)}
          </p>
        )}
      </div>

      <ConfirmDialog
        open={confirming}
        title="Confirmar venta"
        message={`¿Confirmar y cobrar la venta ${sale.sale_number} por ${formatCurrency(sale.total)}? Se descontará el stock de los productos.`}
        busy={busy}
        error={confirming ? actionError : null}
        onConfirm={() => void handleConfirm()}
        onCancel={() => setConfirming(false)}
      />
      <ConfirmDialog
        open={cancelling}
        title="Cancelar venta"
        message={`¿Cancelar la venta ${sale.sale_number}? Quedará en estado CANCELLED y no podrá confirmarse.`}
        destructive
        busy={busy}
        error={cancelling ? actionError : null}
        onConfirm={() => void handleCancel()}
        onCancel={() => setCancelling(false)}
      />
    </div>
  );
}