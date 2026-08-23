import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import {
  createCategory,
  deactivateCategory,
  listCategories,
  updateCategory,
} from '../../services/categories';
import type { ApiCategory } from '../../types/catalog';
import CategoryForm from '../../components/domain/CategoryForm';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import Modal from '../../components/ui/Modal';

export default function CategoriesPage() {
  const { user } = useAuth();
  const [includeInactive, setIncludeInactive] = useState(false);
  const categoriesState = useAsync(() => listCategories(includeInactive), [
    includeInactive,
  ]);

  const canWrite =
    user?.roles.some((role) =>
      ['ADMIN', 'INVENTORY_MANAGER'].includes(role.name),
    ) ?? false;

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ApiCategory | null>(null);
  const [deactivating, setDeactivating] = useState<ApiCategory | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deactivateError, setDeactivateError] = useState<string | null>(null);

  async function handleSubmit(values: { name: string; description: string }) {
    setBusy(true);
    setFormError(null);
    try {
      if (editing) {
        await updateCategory(editing.id, values);
      } else {
        await createCategory(values);
      }
      setFormOpen(false);
      setEditing(null);
      await categoriesState.reload();
    } catch (err) {
      setFormError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleToggleStatus(category: ApiCategory) {
    setBusy(true);
    setFormError(null);
    try {
      await updateCategory(category.id, { is_active: !category.is_active });
      setEditing(null);
      setFormOpen(false);
      await categoriesState.reload();
    } catch (err) {
      setFormError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmDeactivate() {
    if (!deactivating) return;
    setBusy(true);
    setDeactivateError(null);
    try {
      await deactivateCategory(deactivating.id);
      setDeactivating(null);
      await categoriesState.reload();
    } catch (err) {
      setDeactivateError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-gray-900">Categorías</h2>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
              className="rounded border-gray-300"
            />
            Mostrar inactivas
          </label>
          {canWrite && (
            <button
              type="button"
              onClick={() => {
                setEditing(null);
                setFormError(null);
                setFormOpen(true);
              }}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            >
              + Nueva categoría
            </button>
          )}
        </div>
      </div>

      <ErrorAlert
        message={categoriesState.error}
        onRetry={categoriesState.loading ? undefined : () => void categoriesState.reload()}
      />

      <div className="overflow-hidden rounded-lg bg-white shadow">
        {categoriesState.loading ? (
          <p className="px-4 py-10 text-center text-sm text-gray-500">Cargando…</p>
        ) : (categoriesState.data?.length ?? 0) === 0 ? (
          <EmptyState title="Sin categorías" hint="Crea la primera categoría para empezar." />
        ) : (
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Nombre</th>
                <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 sm:table-cell">
                  Descripción
                </th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Estado</th>
                {canWrite && (
                  <th className="px-4 py-3 text-right font-semibold text-gray-600">Acciones</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {categoriesState.data?.map((category) => (
                <tr key={category.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{category.name}</td>
                  <td className="hidden px-4 py-3 text-gray-500 sm:table-cell">
                    {category.description || '—'}
                  </td>
                  <td className="px-4 py-3">
                    {category.is_active ? (
                      <Badge tone="green">Activa</Badge>
                    ) : (
                      <Badge tone="red">Inactiva</Badge>
                    )}
                  </td>
                  {canWrite && (
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => {
                          setEditing(category);
                          setFormError(null);
                          setFormOpen(true);
                        }}
                        className="mr-2 text-sm font-medium text-blue-600 hover:text-blue-800"
                      >
                        Editar
                      </button>
                      {category.is_active && (
                        <button
                          type="button"
                          onClick={() => {
                            setDeactivateError(null);
                            setDeactivating(category);
                          }}
                          className="text-sm font-medium text-red-600 hover:text-red-800"
                        >
                          Desactivar
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal
        open={formOpen}
        title={editing ? `Editar categoría: ${editing.name}` : 'Nueva categoría'}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
        }}
      >
        {editing && canWrite && (
          <div className="mb-4 flex items-center justify-between rounded-md bg-gray-50 px-3 py-2 text-sm">
            <span>Estado actual:</span>
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleToggleStatus(editing)}
              className="font-medium text-blue-600 hover:text-blue-800"
            >
              {editing.is_active ? 'Desactivar' : 'Activar'}
            </button>
          </div>
        )}
        <CategoryForm
          initial={
            editing
              ? {
                  name: editing.name,
                  description: editing.description ?? '',
                }
              : undefined
          }
          busy={busy}
          error={formError}
          submitLabel={editing ? 'Guardar cambios' : 'Crear categoría'}
          onSubmit={(values) => void handleSubmit(values)}
        />
      </Modal>

      <ConfirmDialog
        open={deactivating !== null}
        title="Desactivar categoría"
        message={`¿Desactivar "${deactivating?.name}"? Las categorías con productos asociados no pueden desactivarse.`}
        confirmLabel="Desactivar"
        destructive
        busy={busy}
        error={deactivateError}
        onConfirm={() => void confirmDeactivate()}
        onCancel={() => setDeactivating(null)}
      />
    </div>
  );
}
