import { useState } from 'react';
import { InlineError } from '../ui/ErrorAlert';
import Modal from '../ui/Modal';
import type { ApiProduct } from '../../types/catalog';
import { formatCurrency } from '../../utils/format';

export type StockOperationType = 'ENTRY' | 'EXIT' | 'ADJUSTMENT' | 'RETURN';

const TITLES: Record<StockOperationType, string> = {
  ENTRY: 'Registrar entrada de stock',
  EXIT: 'Registrar salida de stock',
  ADJUSTMENT: 'Ajuste de inventario',
  RETURN: 'Registrar devolución',
};

interface StockOperationModalProps {
  operation: StockOperationType | null;
  product: ApiProduct | null;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSubmitEntryExitReturn: (quantity: number, reason: string, referenceId: string) => void;
  onSubmitAdjustment: (newStock: number, reason: string) => void;
}

export default function StockOperationModal({
  operation,
  product,
  busy,
  error,
  onClose,
  onSubmitEntryExitReturn,
  onSubmitAdjustment,
}: StockOperationModalProps) {
  const [quantity, setQuantity] = useState('1');
  const [newStock, setNewStock] = useState('');
  const [reason, setReason] = useState('');
  const [referenceId, setReferenceId] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  if (!operation || !product) return null;
  const isAdjustment = operation === 'ADJUSTMENT';

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (isAdjustment) {
      const value = Number(newStock);
      if (!Number.isInteger(value) || value < 0) {
        errors.newStock = 'Stock objetivo debe ser un entero ≥ 0';
      } else if (value === product!.stock) {
        errors.newStock = 'El stock no cambia; ajuste innecesario';
      }
      if (!reason.trim()) errors.reason = 'El motivo es obligatorio en ajustes';
    } else {
      const value = Number(quantity);
      if (!Number.isInteger(value) || value <= 0) {
        errors.quantity = 'Cantidad debe ser un entero mayor a 0';
      } else if (operation === 'EXIT' && value > product!.stock) {
        errors.quantity = `Stock insuficiente (disponible: ${product!.stock})`;
      }
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    if (isAdjustment) {
      onSubmitAdjustment(Number(newStock), reason.trim());
    } else {
      onSubmitEntryExitReturn(Number(quantity), reason.trim(), referenceId.trim());
    }
    setQuantity('1');
    setNewStock('');
    setReason('');
    setReferenceId('');
    setFieldErrors({});
  }

  return (
    <Modal open={operation !== null} title={TITLES[operation]} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-sm text-muted">
          {product.name} — stock actual:{' '}
          <span className="font-semibold text-foreground">{product.stock}</span> ·{' '}
          {formatCurrency(product.sale_price)}
        </p>

        <div>
          <label htmlFor="op-quantity" className="nx-label">
            Cantidad <span className="text-red-500">*</span>
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