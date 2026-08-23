import { useState } from 'react';
import { InlineError } from '../ui/ErrorAlert';
import type { CategoryFormValues } from '../../types/catalog';

interface CategoryFormProps {
  initial?: Partial<CategoryFormValues>;
  busy: boolean;
  error: string | null;
  submitLabel: string;
  onSubmit: (values: CategoryFormValues) => void;
}

export default function CategoryForm({
  initial,
  busy,
  error,
  submitLabel,
  onSubmit,
}: CategoryFormProps) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [fieldError, setFieldError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setFieldError('El nombre es obligatorio');
      return;
    }
    setFieldError(null);
    onSubmit({ name, description });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="category-name" className="block text-sm font-medium text-gray-700">
          Nombre <span className="text-red-500">*</span>
        </label>
        <input
          id="category-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={80}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          placeholder="Ej. Lácteos"
        />
        <InlineError message={fieldError} />
      </div>
      <div>
        <label
          htmlFor="category-description"
          className="block text-sm font-medium text-gray-700"
        >
          Descripción
        </label>
        <textarea
          id="category-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={3}
          maxLength={255}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          placeholder="Descripción opcional"
        />
      </div>
      {error && (
        <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {busy ? 'Guardando…' : submitLabel}
        </button>
      </div>
    </form>
  );
}
