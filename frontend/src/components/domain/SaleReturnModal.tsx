import { useMemo, useState } from 'react';
import { extractErrorMessage } from '../../hooks/useAsync';
import { listProducts } from '../../services/products';
import { createSaleReturn } from '../../services/sales';
import type { ApiSaleDetail } from '../../types/sale';
import type {
  ApiSaleReturn,
  RefundMethod,
  ReturnCondition,
} from '../../types/saleReturn';
import {
  refundMethodLabel,
  returnConditionLabel,
} from '../../types/saleReturn';
import { formatCurrency } from '../../utils/format';
import Modal from '../ui/Modal';
import Icon from '../ui/Icon';

type Mode = 'RETURN' | 'EXCHANGE';

interface ReturnLine {
  saleItemId: string;
  productName: string;
  maxQuantity: number;
  alreadyReturned: number;
  unitPrice: string;
  quantity: number;
  condition: ReturnCondition;
}

interface ExchangeLine {
  key: string;
  productId: string;
  name: string;
  quantity: number;
  unitPrice: string;
}

interface Props {
  sale: ApiSaleDetail;
  previouslyReturned: Record<string, number>;
  exchangeCatalog: Awaited<ReturnType<typeof listProducts>>['items'];
  onClose: () => void;
  onCreated: (created: ApiSaleReturn) => void;
}

const REFUND_METHODS: RefundMethod[] = ['CASH', 'CARD', 'TRANSFER', 'CREDIT'];
const CONDITIONS: ReturnCondition[] = ['RESALE', 'DAMAGED', 'REVIEW'];

export default function SaleReturnModal({
  sale,
  previouslyReturned,
  exchangeCatalog,
  onClose,
  onCreated,
}: Props) {
  const [mode, setMode] = useState<Mode>('RETURN');
  const [refundMethod, setRefundMethod] = useState<RefundMethod>(
    sale.payment_method === 'CREDIT' ? 'CREDIT' : 'CASH',
  );
  const [reason, setReason] = useState('');
  const [lines, setLines] = useState<ReturnLine[]>(() =>
    sale.items.map((item) => ({
      saleItemId: item.id,
      productName: item.product_name ?? 'Producto',
      maxQuantity: item.quantity - (previouslyReturned[item.id] ?? 0),
      alreadyReturned: previouslyReturned[item.id] ?? 0,
      unitPrice: item.unit_price,
      quantity: 0,
      condition: 'RESALE' as ReturnCondition,
    })),
  );
  const [exchangeLines, setExchangeLines] = useState<ExchangeLine[]>([]);
  const [showConfirm, setShowConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [idempotencyKey] = useState(() =>
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `ret-${new Date().getTime()}`,
  );

  const returnSubtotal = useMemo(
    () =>
      lines.reduce(
        (sum, line) => sum + Number(line.unitPrice) * line.quantity,
        0,
      ),
    [lines],
  );

  const exchangeSubtotal = useMemo(
    () =>
      exchangeLines.reduce(
        (sum, line) => sum + Number(line.unitPrice) * line.quantity,
        0,
      ),
    [exchangeLines],
  );

  const difference = exchangeSubtotal - returnSubtotal;
  const selectedCount = lines.reduce((sum, line) => sum + line.quantity, 0);
  const invalidOver = lines.some((line) => line.quantity > line.maxQuantity);

  function updateLine(saleItemId: string, patch: Partial<ReturnLine>) {
    setLines((prev) =>
      prev.map((line) =>
        line.saleItemId === saleItemId ? { ...line, ...patch } : line,
      ),
    );
  }

  function fillAll() {
    setLines((prev) =>
      prev.map((line) => ({ ...line, quantity: line.maxQuantity })),
    );
  }

  function addExchangeLine(productId: string) {
    const product = exchangeCatalog.find((p) => p.id === productId);
    if (!product) return;
    setExchangeLines((prev) => [
      ...prev,
      {
        key: `${productId}-${Date.now()}-${prev.length}`,
        productId,
        name: product.name,
        quantity: 1,
        unitPrice: product.sale_price,
      },
    ]);
  }

  function updateExchangeLine(key: string, patch: Partial<ExchangeLine>) {
    setExchangeLines((prev) =>
      prev.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    );
  }

  function removeExchangeLine(key: string) {
    setExchangeLines((prev) => prev.filter((line) => line.key !== key));
  }

  function validate(): string | null {
    if (selectedCount === 0) {
      return 'Selecciona al menos un producto a devolver.';
    }
    if (invalidOver) {
      return 'Alguna cantidad supera lo disponible para devolver.';
    }
    if (mode === 'EXCHANGE' && exchangeLines.length === 0) {
      return 'Un cambio requiere al menos un producto de reemplazo.';
    }
    return null;
  }

  async function submit() {
    const validation = validate();
    if (validation) {
      setError(validation);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createSaleReturn(sale.id, {
        refund_method: refundMethod,
        reason: reason.trim() || null,
        idempotency_key: idempotencyKey,
        items: lines
          .filter((line) => line.quantity > 0)
          .map((line) => ({
            sale_item_id: line.saleItemId,
            quantity: line.quantity,
            condition: line.condition,
          })),
        exchange_items:
          mode === 'EXCHANGE'
            ? exchangeLines.map((line) => ({
                product_id: line.productId,
                quantity: line.quantity,
                unit_price: Number(line.unitPrice),
              }))
            : [],
        exchange_payment_method:
          mode === 'EXCHANGE' ? sale.payment_method : null,
      });
      onCreated(created);
    } catch (err) {
      setError(extractErrorMessage(err));
      setShowConfirm(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open onClose={onClose} title="Devolución o cambio" wide>
      <div className="space-y-4">
        {error && <p className="text-sm text-danger">{error}</p>}

        <div className="flex gap-2">
          {(['RETURN', 'EXCHANGE'] as Mode[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setMode(value)}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-semibold transition-colors ${
                mode === value
                  ? 'border-[var(--nx-primary)] text-primary'
                  : 'border-line text-muted hover:text-foreground'
              }`}
            >
              {value === 'RETURN' ? 'Devolución' : 'Cambio'}
            </button>
          ))}
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-sm font-semibold">Productos a devolver</h4>
            <button
              type="button"
              onClick={fillAll}
              className="text-xs font-medium text-primary hover:underline"
            >
              Devolver todo
            </button>
          </div>
          <div className="overflow-hidden rounded border border-line">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-2">
                <tr>
                  <th className="px-2 py-1">Producto</th>
                  <th className="px-2 py-1">Vendido</th>
                  <th className="px-2 py-1">Devuelto</th>
                  <th className="px-2 py-1">A devolver</th>
                  <th className="px-2 py-1">Condición</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => (
                  <tr key={line.saleItemId} className="border-t border-line">
                    <td className="px-2 py-1">{line.productName}</td>
                    <td className="px-2 py-1">{line.maxQuantity + line.alreadyReturned}</td>
                    <td className="px-2 py-1">{line.alreadyReturned}</td>
                    <td className="px-2 py-1">
                      <input
                        type="number"
                        min={0}
                        max={line.maxQuantity}
                        value={line.quantity}
                        onChange={(e) =>
                          updateLine(line.saleItemId, {
                            quantity: Math.max(
                              0,
                              Math.min(
                                line.maxQuantity,
                                Number(e.target.value) || 0,
                              ),
                            ),
                          })
                        }
                        className="nx-input w-16 py-0.5"
                        disabled={line.maxQuantity === 0}
                      />
                    </td>
                    <td className="px-2 py-1">
                      <select
                        value={line.condition}
                        onChange={(e) =>
                          updateLine(line.saleItemId, {
                            condition: e.target.value as ReturnCondition,
                          })
                        }
                        className="nx-input py-0.5"
                      >
                        {CONDITIONS.map((c) => (
                          <option key={c} value={c}>
                            {returnConditionLabel(c)}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {lines.every((l) => l.maxQuantity === 0) && (
            <p className="mt-2 text-xs text-muted">
              No queda cantidad disponible para devolver en esta venta.
            </p>
          )}
        </div>

        {mode === 'EXCHANGE' && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Productos de reemplazo</h4>
            <select
              value=""
              onChange={(e) => {
                if (e.target.value) addExchangeLine(e.target.value);
                e.target.value = '';
              }}
              className="nx-input"
            >
              <option value="">Agregar producto…</option>
              {exchangeCatalog.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name} — {formatCurrency(product.sale_price)}
                </option>
              ))}
            </select>
            {exchangeLines.map((line) => (
              <div key={line.key} className="flex items-center gap-2 text-sm">
                <span className="flex-1">{line.name}</span>
                <input
                  type="number"
                  min={1}
                  value={line.quantity}
                  onChange={(e) =>
                    updateExchangeLine(line.key, {
                      quantity: Math.max(1, Number(e.target.value) || 1),
                    })
                  }
                  className="nx-input w-16 py-0.5"
                />
                <span className="w-24 text-right">
                  {formatCurrency(Number(line.unitPrice) * line.quantity)}
                </span>
                <button
                  type="button"
                  onClick={() => removeExchangeLine(line.key)}
                  className="text-danger"
                  aria-label="Quitar"
                >
                  <Icon name="trash" size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="return-refund" className="nx-label">
              Método de reembolso
            </label>
            <select
              id="return-refund"
              value={refundMethod}
              onChange={(e) => setRefundMethod(e.target.value as RefundMethod)}
              className="nx-input"
            >
              {REFUND_METHODS.map((m) => (
                <option key={m} value={m}>
                  {refundMethodLabel(m)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="return-reason" className="nx-label">
              Motivo (opcional)
            </label>
            <input
              id="return-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={2000}
              className="nx-input"
              placeholder="Ej. producto en mal estado"
            />
          </div>
        </div>

        <div className="rounded-lg border border-line bg-surface-2 p-3 text-sm">
          <div className="flex justify-between">
            <span>Total devolución</span>
            <span>{formatCurrency(returnSubtotal)}</span>
          </div>
          {mode === 'EXCHANGE' && (
            <>
              <div className="flex justify-between">
                <span>Total cambio</span>
                <span>{formatCurrency(exchangeSubtotal)}</span>
              </div>
              <div className="mt-1 flex justify-between font-semibold">
                <span>{difference >= 0 ? 'Diferencia a pagar' : 'Reembolso'}</span>
                <span>{formatCurrency(Math.abs(difference))}</span>
              </div>
            </>
          )}
        </div>

        {showConfirm ? (
          <div className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-500/40 dark:bg-amber-500/10">
            <p>
              ¿Confirmas registrar la {mode === 'EXCHANGE' ? 'cambio' : 'devolución'}?
              Esta acción es definitiva y ajusta inventario y dinero.
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={submit}
                disabled={busy}
                className="nx-btn nx-btn-primary"
              >
                Sí, confirmar
              </button>
              <button
                type="button"
                onClick={() => setShowConfirm(false)}
                disabled={busy}
                className="nx-btn nx-btn-secondary"
              >
                Cancelar
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => {
              const validation = validate();
              if (validation) {
                setError(validation);
                return;
              }
              setError(null);
              setShowConfirm(true);
            }}
            className="nx-btn nx-btn-primary"
          >
            Registrar {mode === 'EXCHANGE' ? 'cambio' : 'devolución'}
          </button>
        )}
      </div>
    </Modal>
  );
}
