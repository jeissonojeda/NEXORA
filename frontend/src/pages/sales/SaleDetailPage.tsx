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
      <p className="py-10 text-center text-sm text-gray-500">Cargando venta…</p>
    );
  }
  if (saleState.error || !saleState.data) {
    return <ErrorAlert message={saleState.error ?? 'Venta no encontrada'} />;
  }

  const sale = saleState.data;
  const isDraft = sale.status === 'DRAFT';

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/ventas"
          className="text-sm font-medium text-blue-600 hover:text-blue-800"
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
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700"
            >
              Confirmar (cobrar)
            </button>
            <button
              type="button"
              onClick={() => {
                setActionError(null);
                setCancelling(true);
              }}
              className="rounded-md border border-red-300 px-4 py-2 text-sm font-semibold text-red-600 hover:bg-red-50"
            >
              Cancelar venta
            </button>
          </div>
        )}
      </div>

      {actionError && <ErrorAlert message={actionError} />}

      {/* Comprobante */}
      <div className="rounded-lg bg-white p-6 shadow">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-200 pb-4">
          <div>
            <p className="font-mono text-lg font-bold text-gray-900">
              {sale.sale_number}
            </p>
            <p className="mt-1 text-xs text-gray-500">
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
            <dt className="text-xs font-medium uppercase text-gray-500">Cliente</dt>
            <dd className="mt-0.5 text-gray-900">
              {sale.customer?.name ?? 'Consumidor final'}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-gray-500">Método de pago</dt>
            <dd className="mt-0.5 text-gray-900">
              {salePaymentMethodLabel(sale.payment_method)}
            </dd>
          </div>
          {(sale.payment_method === 'CASH' ||
            Number(sale.change_due) > 0) && (
            <div>
              <dt className="text-xs font-medium uppercase text-gray-500">
                Efectivo / Vuelto
              </dt>
              <dd className="mt-0.5 text-gray-900">
                {formatCurrency(sale.amount_paid)}
                {Number(sale.change_due) > 0 &&
                  ` / ${formatCurrency(sale.change_due)}`}
              </dd>
            </div>
          )}
        </dl>

        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-3 py-2 text-left font-semibold text-gray-600">Producto</th>
              <th className="px-3 py-2 text-right font-semibold text-gray-600">Cant.</th>
              <th className="px-3 py-2 text-right font-semibold text-gray-600">Precio</th>
              <th className="px-3 py-2 text-right font-semibold text-gray-600">Importe</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sale.items.map((item) => (
              <tr key={item.id}>
                <td className="px-3 py-2 text-gray-900">{item.product_name ?? '—'}</td>
                <td className="px-3 py-2 text-right text-gray-700">{item.quantity}</td>
                <td className="px-3 py-2 text-right text-gray-700">
                  {formatCurrency(item.unit_price)}
                </td>
                <td className="px-3 py-2 text-right font-medium text-gray-900">
                  {formatCurrency(item.subtotal)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="ml-auto mt-4 max-w-xs space-y-1 text-sm">
          <div className="flex justify-between text-gray-600">
            <span>Subtotal</span>
            <span>{formatCurrency(sale.subtotal)}</span>
          </div>
          <div className="flex justify-between text-red-600">
            <span>Descuento</span>
            <span>−{formatCurrency(sale.discount)}</span>
          </div>
          <div className="flex justify-between text-gray-600">
            <span>Impuesto</span>
            <span>+{formatCurrency(sale.tax)}</span>
          </div>
          <div className="flex justify-between border-t border-gray-200 pt-2 text-base font-bold text-gray-900">
            <span>Total</span>
            <span>{formatCurrency(sale.total)}</span>
          </div>
        </div>

        {sale.notes && (
          <p className="mt-4 rounded-md bg-gray-50 px-3 py-2 text-xs text-gray-600">
            Notas: {sale.notes}
          </p>
        )}
        {sale.confirmed_at && (
          <p className="mt-3 text-right text-xs text-gray-400">
            Confirmada el {formatDateTime(sale.confirmed_at)}
          </p>
        )}
      </div>

      <ConfirmDialog
        open={confirming}
        title="Confirmar venta"
        message={`¿Confirmar y cobrar la venta ${sale.sale_number} por ${formatCurrency(sale.total)}? Se descontará el stock de los productos.`}
        busy={busy}
        error={null}
        onConfirm={() => void handleConfirm()}
        onCancel={() => setConfirming(false)}
      />
      <ConfirmDialog
        open={cancelling}
        title="Cancelar venta"
        message={`¿Cancelar la venta ${sale.sale_number}? Quedará en estado CANCELLED y no podrá confirmarse.`}
        destructive
        busy={busy}
        error={null}
        onConfirm={() => void handleCancel()}
        onCancel={() => setCancelling(false)}
      />
    </div>
  );
}
