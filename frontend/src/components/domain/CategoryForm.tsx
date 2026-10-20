import { useState } from 'react';
import { InlineError } from '../ui/ErrorAlert';
import type { CategoryFormValues } from '../../types/catalog';
import type { ApiTax } from '../../types/settings';

interface CategoryFormProps {
  initial?: Partial<CategoryFormValues>;
  taxes?: ApiTax[];
  busy: boolean;
  error: string | null;
  submitLabel: string;
  onSubmit: (values: CategoryFormValues) => void;
  onCancel?: () => void;
}

export default function CategoryForm({
  initial,
  taxes = [],
  busy,
  error,
  submitLabel,
  onSubmit,
  onCancel,
}: CategoryFormProps) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [taxId, setTaxId] = useState(initial?.tax_id ?? '');
  const [fieldError, setFieldError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setFieldError('El nombre es obligatorio');
      return;
    }
    setFieldError(null);
    onSubmit({ name: name.trim(), description: description.trim() || '', tax_id: taxId || '' });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="category-name" className="nx-label">
          Nombre <span className="text-red-500">*</span>
        </label>
        <input
          id="category-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={80}
          className="nx-input"
          placeholder="Ej. Lácteos"
        />
        <InlineError message={fieldError} />
      </div>
      <div>
        <label htmlFor="category-tax" className="nx-label">
          Impuesto por defecto
        </label>
        <select
          id="category-tax"
          value={taxId}
          onChange={(event) => setTaxId(event.target.value)}
          className="nx-select"
        >
          <option value="">Sin impuesto</option>
          {taxes.map((tax) => (
            <option key={tax.id} value={tax.id}>
              {tax.name} ({tax.rate}%)
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="category-description" className="nx-label">
          Descripción
        </label>
        <textarea
          id="category-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={3}
          maxLength={255}
          className="nx-textarea"
          placeholder="Descripción opcional"
        />
      </div>
      {error && (
        <p role="alert" className="rounded-lg border border-red-300 bg-red-100/60 px-3 py-2 text-sm text-red-800 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="nx-btn nx-btn-secondary"
          >
            Cancelar
          </button>
        )}
        <button type="submit" disabled={busy} className="nx-btn nx-btn-primary">
          {busy ? 'Guardando…' : submitLabel}
        </button>
      </div>
    </form>
  );
}