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
import { userHasPermission } from '../../utils/permissions';
import CategoryForm from '../../components/domain/CategoryForm';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import LoadingState from '../../components/ui/LoadingState';
import Modal from '../../components/ui/Modal';
import PageHeader from '../../components/ui/PageHeader';
import Icon from '../../components/ui/Icon';

export default function CategoriesPage() {
  const { user } = useAuth();
  const [includeInactive, setIncludeInactive] = useState(false);
  const categoriesState = useAsync(() => listCategories(includeInactive), [
    includeInactive,
  ]);

  const canWrite =
    userHasPermission(user, 'categories.create') ||
    userHasPermission(user, 'categories.update');

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
    <div className="animate-fade-in space-y-5">
      <PageHeader
        title="Categorías"
        subtitle="Organiza tus productos por categorías."
        actions={
          <>
            <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-muted">
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={(event) => setIncludeInactive(event.target.checked)}
                className="h-4 w-4 rounded border-line-strong accent-[var(--nx-primary)]"
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
                className="nx-btn nx-btn-primary"
              >
                <Icon name="plus" size={16} />
                Nueva categoría
              </button>
            )}
          </>
        }
      />

      <ErrorAlert
        message={categoriesState.error}
        onRetry={categoriesState.loading ? undefined : () => void categoriesState.reload()}
      />

      <div className="nx-card overflow-hidden">
        {categoriesState.loading ? (
          <div className="p-5">
            <LoadingState rows={4} />
          </div>
        ) : (categoriesState.data?.length ?? 0) === 0 ? (
          <EmptyState
            title="Sin categorías"
            hint="Crea la primera categoría para empezar."
            icon="tag"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="nx-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th className="hidden sm:table-cell">Descripción</th>
                  <th>Estado</th>
                  {canWrite && <th className="text-right">Acciones</th>}
                </tr>
              </thead>
              <tbody>
                {categoriesState.data?.map((category) => (
                  <tr key={category.id}>
                    <td className="font-medium">{category.name}</td>
                    <td className="hidden sm:table-cell">{category.description || '—'}</td>
                    <td>
                      {category.is_active ? (
                        <Badge tone="green">Activa</Badge>
                      ) : (
                        <Badge tone="red">Inactiva</Badge>
                      )}
                    </td>
                    {canWrite && (
                      <td className="whitespace-nowrap text-right">
                        <button
                          type="button"
                          onClick={() => {
                            setEditing(category);
                            setFormError(null);
                            setFormOpen(true);
                          }}
                          className="nx-btn nx-btn-sm nx-btn-ghost text-primary"
                        >
                          <Icon name="pencil" size={14} />
                          Editar
                        </button>
                        {category.is_active && (
                          <button
                            type="button"
                            onClick={() => {
                              setDeactivateError(null);
                              setDeactivating(category);
                            }}
                            className="nx-btn nx-btn-sm nx-btn-ghost text-red-600 dark:text-red-400"
                          >
                            <Icon name="trash" size={14} />
                            Desactivar
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
          <div className="mb-4 flex items-center justify-between rounded-lg bg-surface-2 px-3 py-2 text-sm">
            <span className="text-muted">Estado actual:</span>
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleToggleStatus(editing)}
              className="font-medium text-primary hover:underline"
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