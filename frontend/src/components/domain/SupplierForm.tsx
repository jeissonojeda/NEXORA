import { useState } from 'react';
import { InlineError } from '../ui/ErrorAlert';
import type { SupplierFormValues } from '../../types/catalog';

interface SupplierFormProps {
  initial?: Partial<SupplierFormValues>;
  busy: boolean;
  error: string | null;
  submitLabel: string;
  onSubmit: (values: SupplierFormValues) => void;
}

const EMPTY_VALUES: SupplierFormValues = {
  name: '',
  identification: '',
  contact_name: '',
  phone: '',
  email: '',
  address: '',
  city: '',
  notes: '',
};

export default function SupplierForm({
  initial,
  busy,
  error,
  submitLabel,
  onSubmit,
}: SupplierFormProps) {
  const [values, setValues] = useState<SupplierFormValues>({
    ...EMPTY_VALUES,
    ...initial,
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  function set(field: keyof SupplierFormValues, value: string) {
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
        <label htmlFor="supplier-name" className="nx-label">
          Nombre <span className="text-red-500">*</span>
        </label>
        <input
          id="supplier-name"
          value={values.name}
          onChange={(event) => set('name', event.target.value)}
          className="nx-input"
          placeholder="Ej. Distribuidora Alimenticia S.A."
        />
        <InlineError message={fieldErrors.name} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="supplier-identification" className="nx-label">
            Identificación (cédula jurídica / RUC / NIT)
          </label>
          <input
            id="supplier-identification"
            value={values.identification}
            onChange={(event) => set('identification', event.target.value)}
            className="nx-input"
            placeholder="Ej. 310123456789"
          />
          <InlineError message={fieldErrors.identification} />
        </div>
        <div>
          <label htmlFor="supplier-contact" className="nx-label">
            Nombre de contacto
          </label>
          <input
            id="supplier-contact"
            value={values.contact_name}
            onChange={(event) => set('contact_name', event.target.value)}
            className="nx-input"
            placeholder="Ej. María Rodríguez"
          />
          <InlineError message={fieldErrors.contact_name} />
        </div>

        <div>
          <label htmlFor="supplier-phone" className="nx-label">
            Teléfono
          </label>
          <input
            id="supplier-phone"
            type="tel"
            value={values.phone}
            onChange={(event) => set('phone', event.target.value)}
            className="nx-input"
            placeholder="+506 8888-1234"
          />
          <InlineError message={fieldErrors.phone} />
        </div>
        <div>
          <label htmlFor="supplier-email" className="nx-label">
            Email
          </label>
          <input
            id="supplier-email"
            type="email"
            value={values.email}
            onChange={(event) => set('email', event.target.value)}
            className="nx-input"
            placeholder="ventas@proveedor.com"
          />
          <InlineError message={fieldErrors.email} />
        </div>

        <div>
          <label htmlFor="supplier-address" className="nx-label">
            Dirección
          </label>
          <input
            id="supplier-address"
            value={values.address}
            onChange={(event) => set('address', event.target.value)}
            className="nx-input"
          />
          <InlineError message={fieldErrors.address} />
        </div>
        <div>
          <label htmlFor="supplier-city" className="nx-label">
            Ciudad
          </label>
          <input
            id="supplier-city"
            value={values.city}
            onChange={(event) => set('city', event.target.value)}
            className="nx-input"
          />
          <InlineError message={fieldErrors.city} />
        </div>
      </div>

      <div>
        <label htmlFor="supplier-notes" className="nx-label">
          Notas
        </label>
        <textarea
          id="supplier-notes"
          rows={2}
          value={values.notes}
          onChange={(event) => set('notes', event.target.value)}
          className="nx-textarea"
          placeholder="Condiciones de entrega, días de visita, etc."
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