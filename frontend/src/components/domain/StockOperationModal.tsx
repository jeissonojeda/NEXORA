import { useState } from 'react';
import { InlineError } from '../ui/ErrorAlert';
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div role="dialog" aria-modal="true" className="w-full max-w-md rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <h3 className="text-base font-semibold text-gray-900">{TITLES[operation]}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-4">
          <p className="text-sm text-gray-600">
            {product.name} — stock actual:{' '}
            <span className="font-semibold">{product.stock}</span> ·{' '}
            {formatCurrency(product.sale_price)}
          </p>

          <div>
            <label htmlFor="op-quantity" className="block text-sm font-medium text-gray-700">
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
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
            {isAdjustment && (
              <p className="mt-1 text-xs text-gray-400">
                El stock quedará exactamente en este valor.
              </p>
            )}
            <InlineError message={fieldErrors.quantity ?? fieldErrors.newStock} />
          </div>

          {!isAdjustment && (
            <div>
              <label htmlFor="op-reference" className="block text-sm font-medium text-gray-700">
                Referencia (factura/orden)
              </label>
              <input
                id="op-reference"
                value={referenceId}
                onChange={(event) => setReferenceId(event.target.value)}
                disabled={busy}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
          )}

          <div>
            <label htmlFor="op-reason" className="block text-sm font-medium text-gray-700">
              Motivo{' '}
              {isAdjustment && <span className="text-red-500">*</span>}
            </label>
            <textarea
              id="op-reason"
              rows={2}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              disabled={busy}
              maxLength={255}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
            <InlineError message={fieldErrors.reason} />
          </div>

          {error && (
            <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={busy}
              className={`rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 ${
                isAdjustment ? 'bg-amber-600 hover:bg-amber-700' : 'bg-blue-600 hover:bg-blue-700'
              }`}
            >
              {busy ? 'Procesando…' : 'Confirmar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
