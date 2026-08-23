import api from './api';
import type {
  ApiProduct,
  ApiSupplier,
  ApiSupplierDetail,
  Paginated,
  SupplierFormValues,
  SupplierListFilters,
} from '../types/catalog';

export async function listSuppliers(
  filters: SupplierListFilters = {},
): Promise<Paginated<ApiSupplierDetail>> {
  const params: Record<string, unknown> = {};
  if (filters.q?.trim()) params.q = filters.q.trim();
  if (filters.isActive !== null && filters.isActive !== undefined) {
    params.is_active = filters.isActive;
  }
  if (filters.orderBy) params.order_by = filters.orderBy;
  if (filters.order) params.order = filters.order;
  if (filters.skip) params.skip = filters.skip;
  if (filters.limit) params.limit = filters.limit;
  const { data } = await api.get<Paginated<ApiSupplierDetail>>('/suppliers', {
    params,
  });
  return data;
}

export async function getSupplier(id: string): Promise<ApiSupplierDetail> {
  const { data } = await api.get<ApiSupplierDetail>(`/suppliers/${id}`);
  return data;
}

export async function listSupplierProducts(
  supplierId: string,
  filters: {
    q?: string | null;
    isActive?: boolean | null;
    skip?: number;
    limit?: number;
  } = {},
): Promise<Paginated<ApiProduct>> {
  const params: Record<string, unknown> = {};
  if (filters.q?.trim()) params.q = filters.q.trim();
  if (filters.isActive !== null && filters.isActive !== undefined) {
    params.is_active = filters.isActive;
  }
  if (filters.skip) params.skip = filters.skip;
  if (filters.limit) params.limit = filters.limit;
  const { data } = await api.get<Paginated<ApiProduct>>(
    `/suppliers/${supplierId}/products`,
    { params },
  );
  return data;
}

function buildBody(values: Partial<SupplierFormValues>): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (values.name !== undefined) body.name = values.name.trim();
  const optionalText: (keyof SupplierFormValues)[] = [
    'identification',
    'contact_name',
    'phone',
    'address',
    'city',
    'notes',
  ];
  for (const field of optionalText) {
    if (values[field] !== undefined) {
      body[field] = values[field]?.trim() ? values[field]!.trim() : null;
    }
  }
  if (values.email !== undefined) {
    body.email = values.email?.trim() ? values.email.trim() : null;
  }
  return body;
}

export async function createSupplier(
  values: SupplierFormValues,
): Promise<ApiSupplier> {
  const { data } = await api.post<ApiSupplier>('/suppliers', buildBody(values));
  return data;
}

export async function updateSupplier(
  id: string,
  values: Partial<SupplierFormValues> & { is_active?: boolean },
): Promise<ApiSupplier> {
  const { data } = await api.patch<ApiSupplier>(
    `/suppliers/${id}`,
    buildBody(values),
  );
  return data;
}

export async function deactivateSupplier(id: string): Promise<void> {
  await api.delete(`/suppliers/${id}`);
}
