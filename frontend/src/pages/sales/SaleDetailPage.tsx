import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useSettings } from '../../contexts/SettingsContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import {
  cancelSale,
  confirmSale,
  getSale,
  listSaleReturns,
} from '../../services/sales';
import { listProducts } from '../../services/products';
import type { SaleStatus } from '../../types/sale';
import Icon from '../../components/ui/Icon';
import {
  salePaymentMethodLabel,
  saleStatusLabel,
} from '../../types/sale';
import {
  refundMethodLabel,
  type RefundMethod,
} from '../../types/saleReturn';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import ErrorAlert from '../../components/ui/ErrorAlert';
import SaleReturnModal from '../../components/domain/SaleReturnModal';
import { formatCurrency, formatDateTime } from '../../utils/format';
import { userHasPermission } from '../../utils/permissions';

const STATUS_TONE: Record<SaleStatus, 'gray' | 'green' | 'red'> = {
  DRAFT: 'gray',
  CONFIRMED: 'green',
  CANCELLED: 'red',
};

export default function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { settings } = useSettings();
  const canSell =
    user?.roles.some((role) => ['ADMIN', 'CASHIER'].includes(role.name)) ??
    false;

  const saleState = useAsync(
    () => getSale(id as string),
    [id],
  );

  const returnsState = useAsync(
    () => listSaleReturns(id as string, 0, 100),
    [id],
  );

  const canReturn = userHasPermission(user, 'sales.returns');

  const [returnModalOpen, setReturnModalOpen] = useState(false);
  const exchangeCatalogState = useAsync(
    () => listProducts({ isActive: true, limit: 200 }),
    [],
  );
  const exchangeCatalog = exchangeCatalogState.data?.items ?? [];

  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  // Impresión automática al llegar desde el POS ("Ver / imprimir").
  const location = useLocation();
  const autoPrint = Boolean(
    (location.state as { autoPrint?: boolean } | null)?.autoPrint,
  );
  const printedRef = useRef(false);
  useEffect(() => {
    if (!autoPrint || !saleState.data || printedRef.current) return;
    printedRef.current = true;
    const timer = window.setTimeout(() => window.print(), 500);
    return () => window.clearTimeout(timer);
  }, [autoPrint, saleState.data]);

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
  const isConfirmed = sale.status === 'CONFIRMED';
  const returns = returnsState.data?.items ?? [];
  const previouslyReturned = returns
    .filter((r) => r.status !== 'CANCELLED')
    .flatMap((r) => r.items)
    .reduce<Record<string, number>>((acc, item) => {
      acc[item.sale_item_id] = (acc[item.sale_item_id] ?? 0) + item.quantity;
      return acc;
    }, {});
  const totalReturned = returns
    .filter((r) => r.status !== 'CANCELLED')
    .reduce((sum, r) => sum + Number(r.refunded_amount), 0);

  // Desglose de impuestos agrupado por nombre + tasa (snapshot histórico del ítem).
  const taxGroups = Object.values(
    sale.items.reduce<
      Record<string, { name: string; rate: number; base: number; tax: number }>
    >((acc, item) => {
      const rate = Number(item.tax_rate) || 0;
      if (rate <= 0) return acc;
      const key = `${item.tax_name ?? 'Impuesto'}-${rate}`;
      const base = Number(item.subtotal);
      if (!acc[key]) {
        acc[key] = { name: item.tax_name ?? 'Impuesto', rate, base: 0, tax: 0 };
      }
      acc[key].base += base;
      acc[key].tax += Number(item.tax) || 0;
      return acc;
    }, {}),
  );

  const paperWidth = settings?.paper_width ?? '80mm';
  const paperCss =
    paperWidth === '58mm' || paperWidth === '80mm'
      ? paperWidth
      : paperWidth.toLowerCase();

  return (
    <div className="mx-auto max-w-3xl animate-fade-in space-y-4">
      <style>{`@media print { @page { size: ${paperCss} auto; margin: 4mm; } }`}</style>
      <div className="nx-no-print flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/ventas"
          className="text-sm font-medium text-primary hover:underline"
        >
          ← Volver a ventas
        </Link>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => window.print()}
            className="nx-btn nx-btn-secondary"
          >
            <Icon name="printer" size={16} />
            Imprimir
          </button>
          {canReturn && isConfirmed && (
            <button
              type="button"
              onClick={() => {
                setActionError(null);
                setReturnModalOpen(true);
              }}
              className="nx-btn nx-btn-primary"
            >
              <Icon name="refresh" size={16} />
              Devolución / Cambio
            </button>
          )}
        </div>
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

      {/* Comprobante (pantalla) */}
      <div className="nx-no-print nx-card p-6">
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
          {taxGroups.map((group) => (
            <div
              key={`${group.name}-${group.rate}`}
              className="flex justify-between text-muted"
            >
              <span>
                {group.name} ({group.rate}%)
              </span>
              <span className="tabular-nums">+{formatCurrency(group.tax)}</span>
            </div>
          ))}
          {taxGroups.length === 0 && (
            <div className="flex justify-between text-muted">
              <span>Impuesto</span>
              <span className="tabular-nums">+{formatCurrency(sale.tax)}</span>
            </div>
          )}
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

      {/* Comprobante imprimible */}
      <div
        className="nx-print-area hidden print:block"
        style={{ fontSize: settings?.print_font_size ?? '12px' }}
      >
        <div style={{ textAlign: 'center', marginBottom: '6px' }}>
          <div style={{ fontWeight: 700, fontSize: '1.1em' }}>
            {settings?.business_name ?? 'NEXORA'}
          </div>
          {settings?.print_show_tax_id && settings?.business_tax_id && (
            <div>NIT: {settings.business_tax_id}</div>
          )}
          {settings?.print_show_contact && (
            <>
              {settings?.business_address && <div>{settings.business_address}</div>}
              {settings?.business_phone && <div>Tel: {settings.business_phone}</div>}
              {settings?.business_email && <div>{settings.business_email}</div>}
            </>
          )}
        </div>
        <div style={{ borderTop: '1px dashed #000', margin: '4px 0' }} />
        <div>Comprobante: {sale.sale_number}</div>
        <div>Fecha: {formatDateTime(sale.created_at)}</div>
        <div>Cajero: {sale.created_by_username ?? '—'}</div>
        <div>Cliente: {sale.customer?.name ?? 'Consumidor final'}</div>
        <div style={{ borderTop: '1px dashed #000', margin: '4px 0' }} />
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>Producto</th>
              <th style={{ textAlign: 'right' }}>Cant</th>
              <th style={{ textAlign: 'right' }}>Importe</th>
            </tr>
          </thead>
          <tbody>
            {sale.items.map((item) => (
              <tr key={item.id}>
                <td>
                  {item.product_name ?? '—'}
                  {Number(item.tax_rate) > 0 && (
                    <span style={{ fontSize: '0.85em' }}>
                      {' '}
                      ({item.tax_name ?? 'Impuesto'} {item.tax_rate}%)
                    </span>
                  )}
                </td>
                <td style={{ textAlign: 'right' }}>{item.quantity}</td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  {formatCurrency(item.subtotal)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ borderTop: '1px dashed #000', margin: '4px 0' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Subtotal</span>
          <span>{formatCurrency(sale.subtotal)}</span>
        </div>
        {Number(sale.discount) > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Descuento</span>
            <span>-{formatCurrency(sale.discount)}</span>
          </div>
        )}
        {taxGroups.map((group) => (
          <div
            key={`print-${group.name}-${group.rate}`}
            style={{ display: 'flex', justifyContent: 'space-between' }}
          >
            <span>
              {group.name} ({group.rate}%)
            </span>
            <span>{formatCurrency(group.tax)}</span>
          </div>
        ))}
        {taxGroups.length === 0 && Number(sale.tax) > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Impuesto</span>
            <span>{formatCurrency(sale.tax)}</span>
          </div>
        )}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontWeight: 700,
            borderTop: '1px solid #000',
            marginTop: '4px',
            paddingTop: '4px',
          }}
        >
          <span>TOTAL</span>
          <span>{formatCurrency(sale.total)}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Pago ({salePaymentMethodLabel(sale.payment_method)})</span>
          <span>{formatCurrency(sale.amount_paid)}</span>
        </div>
        {Number(sale.change_due) > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Cambio</span>
            <span>{formatCurrency(sale.change_due)}</span>
          </div>
        )}
        <div style={{ borderTop: '1px dashed #000', margin: '6px 0 4px' }} />
        <div style={{ textAlign: 'center' }}>
          {settings?.print_footer_text ?? '¡Gracias por su compra!'}
        </div>
      </div>

      {/* Historial de devoluciones/cambios */}
      {returns.length > 0 && (
        <div className="nx-no-print nx-card p-6">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-widest text-faint">
              Devoluciones y cambios
            </h2>
            <Badge tone="amber">Reembolsado: {formatCurrency(totalReturned)}</Badge>
          </div>
          <div className="space-y-3">
            {returns.map((r) => (
              <div
                key={r.id}
                className="rounded-lg border border-line p-3 text-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono font-semibold text-foreground">
                    {r.return_number}
                  </span>
                  <span className="flex items-center gap-2">
                    <Badge tone={r.return_type === 'EXCHANGE' ? 'blue' : 'gray'}>
                      {r.return_type === 'EXCHANGE' ? 'Cambio' : 'Devolución'}
                    </Badge>
                    {r.status === 'CANCELLED' && (
                      <Badge tone="red">Anulada</Badge>
                    )}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted">
                  {formatDateTime(r.created_at)} ·{' '}
                  {refundMethodLabel(r.refund_method as RefundMethod)}
                  {r.exchange_sale_number &&
                    ` · Venta cambio: ${r.exchange_sale_number}`}
                </div>
                {r.reason && (
                  <p className="mt-1 text-xs text-muted">Motivo: {r.reason}</p>
                )}
                <ul className="mt-2 space-y-0.5 text-xs">
                  {r.items.map((item) => (
                    <li key={item.id}>
                      {item.quantity}× {item.product_name ?? 'Producto'} —{' '}
                      {formatCurrency(item.total)}
                    </li>
                  ))}
                </ul>
                <div className="mt-2 flex flex-wrap gap-3 text-xs font-medium">
                  <span>Total devuelto: {formatCurrency(r.total)}</span>
                  {Number(r.refunded_amount) > 0 && (
                    <span>Reembolsado: {formatCurrency(r.refunded_amount)}</span>
                  )}
                  {Number(r.credit_applied) > 0 && (
                    <span>Crédito aplicado: {formatCurrency(r.credit_applied)}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {returnModalOpen && (
        <SaleReturnModal
          sale={sale}
          previouslyReturned={previouslyReturned}
          exchangeCatalog={exchangeCatalog}
          onClose={() => setReturnModalOpen(false)}
          onCreated={() => {
            setReturnModalOpen(false);
            void returnsState.reload();
            void saleState.reload();
          }}
        />
      )}

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