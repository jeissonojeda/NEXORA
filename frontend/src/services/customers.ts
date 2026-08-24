import api from './api';
import type {
  ApiCustomer,
  CustomerFormValues,
  CustomerListFilters,
} from '../types/customer';

export async function listCustomers(
  filters: CustomerListFilters = {},
): Promise<{ items: ApiCustomer[]; total: number }> {
  const params: Record<string, unknown> = {};
  if (filters.q?.trim()) params.q = filters.q.trim();
  if (filters.isActive !== null && filters.isActive !== undefined) {
    params.is_active = filters.isActive;
  }
  if (filters.creditEnabled !== null && filters.creditEnabled !== undefined) {
    params.credit_enabled = filters.creditEnabled;
  }
  if (filters.orderBy) params.order_by = filters.orderBy;
  if (filters.order) params.order = filters.order;
  if (filters.skip) params.skip = filters.skip;
  if (filters.limit) params.limit = filters.limit;
  const { data } = await api.get<{ items: ApiCustomer[]; total: number }>(
    '/customers',
    { params },
  );
  return data;
}

export async function getCustomer(id: string): Promise<ApiCustomer> {
  const { data } = await api.get<ApiCustomer>(`/customers/${id}`);
  return data;
}

function buildBody(
  values: Partial<CustomerFormValues>,
): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (values.name !== undefined) body.name = values.name.trim();
  const optionalText: (
    | 'identification'
    | 'phone'
    | 'address'
    | 'city'
    | 'notes'
  )[] = ['identification', 'phone', 'address', 'city', 'notes'];
  for (const field of optionalText) {
    if (values[field] !== undefined) {
      body[field] = values[field]?.trim() ? values[field]!.trim() : null;
    }
  }
  if (values.email !== undefined) {
    body.email = values.email?.trim() ? values.email.trim() : null;
  }
  if (values.credit_enabled !== undefined) {
    body.credit_enabled = values.credit_enabled;
  }
  if (values.credit_limit !== undefined && values.credit_limit.trim() !== '') {
    body.credit_limit = values.credit_limit.trim();
  }
  return body;
}

export async function createCustomer(
  values: CustomerFormValues,
): Promise<ApiCustomer> {
  const { data } = await api.post<ApiCustomer>('/customers', buildBody(values));
  return data;
}

export async function updateCustomer(
  id: string,
  values: Partial<CustomerFormValues> & { is_active?: boolean },
): Promise<ApiCustomer> {
  const { data } = await api.patch<ApiCustomer>(
    `/customers/${id}`,
    buildBody(values),
  );
  return data;
}

export async function deactivateCustomer(id: string): Promise<void> {
  await api.delete(`/customers/${id}`);
}