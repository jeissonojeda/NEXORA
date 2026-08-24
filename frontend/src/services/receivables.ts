import api from './api';
import type {
  ApiCustomerStatement,
  ApiReceivableAccount,
  ApiReceivablePayment,
  ReceivableCreatePayload,
  ReceivablePaymentPayload,
} from '../types/customer';
import type { Paginated } from '../types/catalog';

export async function listReceivables(filters: {
  customerId?: string | null;
  status?: string | null;
  skip?: number;
  limit?: number;
}): Promise<Paginated<ApiReceivableAccount>> {
  const params: Record<string, unknown> = {};
  if (filters.customerId) params.customer_id = filters.customerId;
  if (filters.status) params.status = filters.status;
  if (filters.skip) params.skip = filters.skip;
  if (filters.limit) params.limit = filters.limit;
  const { data } = await api.get<Paginated<ApiReceivableAccount>>(
    '/receivables',
    { params },
  );
  return data;
}

export async function getReceivable(
  id: string,
): Promise<ApiReceivableAccount> {
  const { data } = await api.get<ApiReceivableAccount>(`/receivables/${id}`);
  return data;
}

export async function createReceivable(
  payload: ReceivableCreatePayload,
): Promise<ApiReceivableAccount> {
  const { data } = await api.post<ApiReceivableAccount>(
    '/receivables',
    payload,
  );
  return data;
}

export async function listReceivablePayments(
  accountId: string,
  skip = 0,
  limit = 50,
): Promise<Paginated<ApiReceivablePayment>> {
  const { data } = await api.get<Paginated<ApiReceivablePayment>>(
    `/receivables/${accountId}/payments`,
    { params: { skip, limit } },
  );
  return data;
}

export async function registerPayment(
  accountId: string,
  payload: ReceivablePaymentPayload,
): Promise<ApiReceivablePayment> {
  const body: Record<string, unknown> = {
    amount: payload.amount,
    payment_method: payload.payment_method,
  };
  if (payload.reference?.trim()) body.reference = payload.reference.trim();
  if (payload.notes?.trim()) body.notes = payload.notes.trim();
  if (payload.idempotency_key) body.idempotency_key = payload.idempotency_key;
  const { data } = await api.post<ApiReceivablePayment>(
    `/receivables/${accountId}/payments`,
    body,
  );
  return data;
}

export async function cancelReceivable(
  id: string,
): Promise<ApiReceivableAccount> {
  const { data } = await api.post<ApiReceivableAccount>(
    `/receivables/${id}/cancel`,
  );
  return data;
}

export async function getCustomerStatement(
  customerId: string,
): Promise<ApiCustomerStatement> {
  const { data } = await api.get<ApiCustomerStatement>(
    `/customers/${customerId}/statement`,
  );
  return data;
}
