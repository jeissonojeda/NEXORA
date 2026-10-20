import { useState } from 'react';
import { InlineError } from '../ui/ErrorAlert';
import Modal from '../ui/Modal';
import type { ApiProduct } from '../../types/catalog';
import { formatCurrency } from '../../utils/format';

export type StockOperationType = 'ENTRY' | 'EXIT' | 'ADJUSTMENT' | 'RETURN';

const STOCK_OPERATION_LABELS: Record<StockOperationType, string> = {
  ENTRY: 'Entrada',
  EXIT: 'Salida',
  ADJUSTMENT: 'Ajuste',
  RETURN: 'Devolución',
};

const TITLES: Record<StockOperationType, string> = {
  ENTRY: 'Registrar entrada de stock',
  EXIT: 'Registrar salida de stock',
  ADJUSTMENT: 'Ajuste de inventario',
  RETURN: 'Registrar devolución',
};

const OPERATION_HINTS: Record<StockOperationType, string> = {
  ENTRY: 'Ingresa unidades al inventario (compra, carga inicial, etc.).',
  EXIT: 'Retira unidades por merma, consumo o traslado.',
  ADJUSTMENT: 'Fija el stock exacto tras un conteo físico.',
  RETURN: 'Reingresa unidades devueltas por un cliente.',
};

interface StockOperationModalProps {
  open: boolean;
  product: ApiProduct | null;
  products?: ApiProduct[];
  initialOperation?: StockOperationType;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSubmitEntryExitReturn: (
    productId: string,
    operation: StockOperationType,
    quantity: number,
    reason: string,
    referenceId: string,
  ) => void;
  onSubmitAdjustment: (productId: string, newStock: number, reason: string) => void;
}

const OPERATIONS: StockOperationType[] = ['ENTRY', 'EXIT', 'RETURN', 'ADJUSTMENT'];

export default function StockOperationModal({
  open,
  product,
  products = [],
  initialOperation = 'ENTRY',
  busy,
  error,
  onClose,
  onSubmitEntryExitReturn,
  onSubmitAdjustment,
}: StockOperationModalProps) {
  const [operation, setOperation] = useState<StockOperationType>(initialOperation);
  const [selectedProductId, setSelectedProductId] = useState(product?.id ?? '');
  const [quantity, setQuantity] = useState('1');
  const [newStock, setNewStock] = useState(product ? String(product.stock) : '');
  const [reason, setReason] = useState('');
  const [referenceId, setReferenceId] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const effectiveProduct =
    product ?? products.find((item) => item.id === selectedProductId) ?? null;
  const isAdjustment = operation === 'ADJUSTMENT';

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const errors: Record<string, string> = {};

    if (!effectiveProduct) {
      errors.product = 'Selecciona un producto';
    }
    if (isAdjustment) {
      const value = Number(newStock);
      if (!Number.isInteger(value) || value < 0) {
        errors.newStock = 'Stock objetivo debe ser un entero ≥ 0';
      } else if (effectiveProduct && value === effectiveProduct.stock) {
        errors.newStock = 'El stock no cambia; ajuste innecesario';
      }
      if (!reason.trim()) errors.reason = 'El motivo es obligatorio en ajustes';
    } else {
      const value = Number(quantity);
      if (!Number.isInteger(value) || value <= 0) {
        errors.quantity = 'Cantidad debe ser un entero mayor a 0';
      } else if (
        operation === 'EXIT' &&
        effectiveProduct &&
        value > effectiveProduct.stock
      ) {
        errors.quantity = `Stock insuficiente (disponible: ${effectiveProduct.stock})`;
      }
    }

    setFieldErrors(errors);
    if (Object.keys(errors).length > 0 || !effectiveProduct) return;

    if (isAdjustment) {
      onSubmitAdjustment(effectiveProduct.id, Number(newStock), reason.trim());
    } else {
      onSubmitEntryExitReturn(
        effectiveProduct.id,
        operation,
        Number(quantity),
        reason.trim(),
        referenceId.trim(),
      );
    }
  }

  return (
    <Modal open={open} title={TITLES[operation]} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div
          role="tablist"
          aria-label="Tipo de movimiento"
          className="grid grid-cols-2 gap-1 rounded-xl bg-surface-2 p-1 sm:grid-cols-4"
        >
          {OPERATIONS.map((item) => (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={operation === item}
              onClick={() => {
                setOperation(item);
                setFieldErrors({});
              }}
              disabled={busy}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                operation === item
                  ? 'bg-surface text-foreground shadow-sm'
                  : 'text-muted hover:text-foreground'
              }`}
            >
              {STOCK_OPERATION_LABELS[item]}
            </button>
          ))}
        </div>

        <p className="text-xs text-faint">{OPERATION_HINTS[operation]}</p>

        {product ? (
          <p className="text-sm text-muted">
            {product.name} — stock actual:{' '}
            <span className="font-semibold text-foreground">{product.stock}</span> ·{' '}
            {formatCurrency(product.sale_price)}
          </p>
        ) : (
          <div>
            <label htmlFor="op-product" className="nx-label">
              Producto <span className="text-red-500">*</span>
            </label>
            <select
              id="op-product"
              value={selectedProductId}
              onChange={(event) => {
                setSelectedProductId(event.target.value);
                const next = products.find((item) => item.id === event.target.value);
                setNewStock(next ? String(next.stock) : '');
              }}
              disabled={busy}
              className="nx-select"
            >
              <option value="">Seleccionar producto…</option>
              {products.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} (stock {item.stock})
                </option>
              ))}
            </select>
            <InlineError message={fieldErrors.product} />
          </div>
        )}

        <div>
          <label htmlFor="op-quantity" className="nx-label">
            {isAdjustment ? 'Stock objetivo' : 'Cantidad'}{' '}
            <span className="text-red-500">*</span>
          </label>
          <input
            id="op-quantity"
            type="number"
            step="1"
            min={isAdjustment ? undefined : 1}
            value={isAdjustment ? newStock : quantity}
            onChange={(event) =>
              isAdjustment
                ? setNewStock(event.target.value)
                : setQuantity(event.target.value)
            }
            disabled={busy}
            className="nx-input"
          />
          {isAdjustment && (
            <p className="mt-1 text-xs text-faint">
              El stock quedará exactamente en este valor.
            </p>
          )}
          <InlineError message={fieldErrors.quantity ?? fieldErrors.newStock} />
        </div>

        {!isAdjustment && (
          <div>
            <label htmlFor="op-reference" className="nx-label">
              Referencia (factura/orden)
            </label>
            <input
              id="op-reference"
              value={referenceId}
              onChange={(event) => setReferenceId(event.target.value)}
              disabled={busy}
              className="nx-input"
            />
          </div>
        )}

        <div>
          <label htmlFor="op-reason" className="nx-label">
            Motivo
            {isAdjustment && <span className="text-red-500"> *</span>}
          </label>
          <textarea
            id="op-reason"
            rows={2}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            disabled={busy}
            maxLength={255}
            className="nx-textarea"
          />
          <InlineError message={fieldErrors.reason} />
        </div>

        {error && (
          <p role="alert" className="rounded-lg border border-red-300 bg-red-100/60 px-3 py-2 text-sm text-red-800 dark:bg-red-500/10 dark:text-red-300">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={busy} className="nx-btn nx-btn-secondary">
            Cancelar
          </button>
          <button
            type="submit"
            disabled={busy}
            className={`nx-btn ${isAdjustment ? 'nx-btn-danger' : 'nx-btn-primary'}`}
          >
            {busy ? 'Procesando…' : 'Confirmar'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
