import { useState } from 'react';
import type {
  ApiReceivableAccount,
  PaymentMethod,
  ReceivablePaymentPayload,
} from '../../types/customer';
import { formatCurrency } from '../../utils/format';
import { InlineError } from '../ui/ErrorAlert';

interface PaymentModalProps {
  account: ApiReceivableAccount;
  busy: boolean;
  error: string | null;
  submitLabel: string;
  onSubmit: (payload: ReceivablePaymentPayload) => void;
}

const inputClass =
  'mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none';

const METHODS: { value: PaymentMethod; label: string }[] = [
  { value: 'CASH', label: 'Efectivo' },
  { value: 'CARD', label: 'Tarjeta' },
  { value: 'TRANSFER', label: 'Transferencia' },
  { value: 'OTHER', label: 'Otro' },
];

export default function PaymentModal({
  account,
  busy,
  error,
  submitLabel,
  onSubmit,
}: PaymentModalProps) {
  // Clave estable mientras el modal está abierto: reintentos tras un error
  // de red nunca aplican el pago dos veces.
  const [idempotencyKey] = useState<string | null>(() =>
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : null,
  );

  const balance = Number(account.balance);
  const [amount, setAmount] = useState(balance.toFixed(2));
  const [method, setMethod] = useState<PaymentMethod>('CASH');
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    const value = Number(amount);
    if (!amount.trim() || Number.isNaN(value) || value <= 0) {
      errors.amount = 'Ingrese un monto mayor que cero';
    } else if (value > balance) {
      errors.amount = `El pago no puede exceder el saldo (${formatCurrency(account.balance)})`;
    }
    if (reference.trim().length > 100) {
      errors.reference = 'Máximo 100 caracteres';
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    onSubmit({
      amount: value.toFixed(2),
      payment_method: method,
      reference: reference.trim() || null,
      notes: notes.trim() || null,
      idempotency_key: idempotencyKey,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="rounded-md bg-gray-50 px-3 py-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-500">Saldo pendiente</span>
          <span className="font-semibold tabular-nums text-gray-900">
            {formatCurrency(account.balance)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="payment-amount" className="block text-sm font-medium text-gray-700">
            Monto del abono <span className="text-red-500">*</span>
          </label>
          <input
            id="payment-amount"
            type="number"
            min="0.01"
            step="0.01"
            max={balance}
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className={inputClass}
          />
          <InlineError message={fieldErrors.amount} />
        </div>
        <div>
          <label htmlFor="payment-method" className="block text-sm font-medium text-gray-700">
            Método <span className="text-red-500">*</span>
          </label>
          <select
            id="payment-method"
            value={method}
            onChange={(event) => setMethod(event.target.value as PaymentMethod)}
            className={inputClass}
          >
            {METHODS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label htmlFor="payment-reference" className="block text-sm font-medium text-gray-700">
          Referencia (N° recibo, voucher, transferencia…)
        </label>
        <input
          id="payment-reference"
          value={reference}
          onChange={(event) => setReference(event.target.value)}
          className={inputClass}
        />
        <InlineError message={fieldErrors.reference} />
      </div>

      <div>
        <label htmlFor="payment-notes" className="block text-sm font-medium text-gray-700">
          Notas
        </label>
        <textarea
          id="payment-notes"
          rows={2}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          className={inputClass}
        />
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {busy ? 'Registrando…' : submitLabel}
        </button>
      </div>
    </form>
  );
}
