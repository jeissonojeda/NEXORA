import api from './api';
import type { ApiCategory, CategoryFormValues } from '../types/catalog';

export async function listCategories(includeInactive = false): Promise<ApiCategory[]> {
  const { data } = await api.get<ApiCategory[]>('/categories', {
    params: includeInactive ? { include_inactive: true } : undefined,
  });
  return data;
}

export async function getCategory(id: string): Promise<ApiCategory> {
  const { data } = await api.get<ApiCategory>(`/categories/${id}`);
  return data;
}

export async function createCategory(
  values: CategoryFormValues,
): Promise<ApiCategory> {
  const body: Record<string, unknown> = { name: values.name.trim() };
  if (values.description !== undefined) {
    body.description = values.description?.trim() ? values.description.trim() : null;
  }
  if (values.tax_id !== undefined) {
    body.tax_id = values.tax_id ? values.tax_id : null;
  }
  const { data } = await api.post<ApiCategory>('/categories', body);
  return data;
}

export async function updateCategory(
  id: string,
  values: Partial<CategoryFormValues> & { is_active?: boolean },
): Promise<ApiCategory> {
  const body: Record<string, unknown> = {};
  if (values.name !== undefined) body.name = values.name.trim();
  if (values.description !== undefined) {
    body.description = values.description?.trim() ? values.description.trim() : null;
  }
  if (values.tax_id !== undefined) {
    body.tax_id = values.tax_id ? values.tax_id : null;
  }
  if (values.is_active !== undefined) body.is_active = values.is_active;
  const { data } = await api.patch<ApiCategory>(`/categories/${id}`, body);
  return data;
}

export async function deactivateCategory(id: string): Promise<void> {
  await api.delete(`/categories/${id}`);
}
