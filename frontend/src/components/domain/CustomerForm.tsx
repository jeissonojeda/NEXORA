import { useState } from 'react';
import { InlineError } from '../ui/ErrorAlert';
import type { CustomerFormValues } from '../../types/customer';

interface CustomerFormProps {
  initial?: Partial<CustomerFormValues>;
  busy: boolean;
  error: string | null;
  submitLabel: string;
  onSubmit: (values: CustomerFormValues) => void;
}

const EMPTY_VALUES: CustomerFormValues = {
  name: '',
  identification: '',
  phone: '',
  email: '',
  address: '',
  city: '',
  notes: '',
  credit_enabled: false,
  credit_limit: '',
};

export default function CustomerForm({
  initial,
  busy,
  error,
  submitLabel,
  onSubmit,
}: CustomerFormProps) {
  const [values, setValues] = useState<CustomerFormValues>({
    ...EMPTY_VALUES,
    ...initial,
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  function set(field: keyof CustomerFormValues, value: string | boolean) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!values.name.trim()) {
      errors.name = 'El nombre es obligatorio';
    } else if (values.name.trim().length > 150) {
      errors.name = 'Máximo 150 caracteres';
    }
    if (values.identification.trim() && values.identification.trim().length > 50) {
      errors.identification = 'Máximo 50 caracteres';
    }
    if (values.phone.trim() && values.phone.trim().length > 50) {
      errors.phone = 'Máximo 50 caracteres';
    }
    if (values.email.trim()) {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
        errors.email = 'Ingrese un email válido';
      } else if (values.email.trim().length > 255) {
        errors.email = 'Máximo 255 caracteres';
      }
    }
    if (values.credit_enabled) {
      const limit = Number(values.credit_limit);
      if (!values.credit_limit.trim() || Number.isNaN(limit) || limit <= 0) {
        errors.credit_limit =
          'Defina un límite de crédito mayor que cero para habilitar el crédito';
      }
    } else if (values.credit_limit.trim()) {
      const limit = Number(values.credit_limit);
      if (Number.isNaN(limit) || limit < 0) {
        errors.credit_limit = 'El límite debe ser un número no negativo';
      }
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!validate()) return;
    onSubmit(values);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="customer-name" className="nx-label">
          Nombre <span className="text-red-500">*</span>
        </label>
        <input
          id="customer-name"
          value={values.name}
          onChange={(event) => set('name', event.target.value)}
          className="nx-input"
          placeholder="Ej. Juan Pérez o Minimarket La Esquina"
        />
        <InlineError message={fieldErrors.name} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="customer-identification" className="nx-label">
            Identificación (cédula / RUC / NIT)
          </label>
          <input
            id="customer-identification"
            value={values.identification}
            onChange={(event) => set('identification', event.target.value)}
            className="nx-input"
            placeholder="Ej. 1090123456"
          />
          <InlineError message={fieldErrors.identification} />
        </div>
        <div>
          <label htmlFor="customer-phone" className="nx-label">
            Teléfono
          </label>
          <input
            id="customer-phone"
            type="tel"
            value={values.phone}
            onChange={(event) => set('phone', event.target.value)}
            className="nx-input"
            placeholder="+506 8888-1234"
          />
          <InlineError message={fieldErrors.phone} />
        </div>

        <div>
          <label htmlFor="customer-email" className="nx-label">
            Email
          </label>
          <input
            id="customer-email"
            type="email"
            value={values.email}
            onChange={(event) => set('email', event.target.value)}
            className="nx-input"
          />
          <InlineError message={fieldErrors.email} />
        </div>
        <div>
          <label htmlFor="customer-city" className="nx-label">
            Ciudad
          </label>
          <input
            id="customer-city"
            value={values.city}
            onChange={(event) => set('city', event.target.value)}
            className="nx-input"
          />
          <InlineError message={fieldErrors.city} />
        </div>

        <div className="sm:col-span-2">
          <label htmlFor="customer-address" className="nx-label">
            Dirección
          </label>
          <input
            id="customer-address"
            value={values.address}
            onChange={(event) => set('address', event.target.value)}
            className="nx-input"
          />
          <InlineError message={fieldErrors.address} />
        </div>
      </div>

      {/* Crédito */}
      <fieldset className="rounded-xl border border-line p-4">
        <legend className="px-2 text-sm font-semibold text-muted">Crédito</legend>
        <label
          htmlFor="customer-credit-enabled"
          className="flex cursor-pointer items-center gap-2 text-sm text-foreground"
        >
          <input
            id="customer-credit-enabled"
            type="checkbox"
            checked={values.credit_enabled}
            onChange={(event) => set('credit_enabled', event.target.checked)}
            className="h-4 w-4 rounded border-line-strong accent-[var(--nx-primary)]"
          />
          Cliente autorizado para comprar a crédito
        </label>
        <div className="mt-3 max-w-[220px]">
          <label htmlFor="customer-credit-limit" className="nx-label">
            Límite de crédito (₡)
          </label>
          <input
            id="customer-credit-limit"
            type="number"
            min="0"
            step="0.01"
            disabled={!values.credit_enabled && !values.credit_limit}
            value={values.credit_limit}
            onChange={(event) => set('credit_limit', event.target.value)}
            className="nx-input"
            placeholder="0.00"
          />
          <InlineError message={fieldErrors.credit_limit} />
        </div>
      </fieldset>

      <div>
        <label htmlFor="customer-notes" className="nx-label">
          Notas
        </label>
        <textarea
          id="customer-notes"
          rows={2}
          value={values.notes}
          onChange={(event) => set('notes', event.target.value)}
          className="nx-textarea"
        />
        <InlineError message={fieldErrors.notes} />
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-red-300 bg-red-100/60 px-3 py-2 text-sm text-red-800 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <button type="submit" disabled={busy} className="nx-btn nx-btn-primary">
          {busy ? 'Guardando…' : submitLabel}
        </button>
      </div>
    </form>
  );
}