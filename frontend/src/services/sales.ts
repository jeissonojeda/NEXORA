import api from './api';
import type {
  ApiSaleDetail,
  CreateSalePayload,
  PaginatedSales,
  SaleListFilters,
} from '../types/sale';
import type {
  ApiSaleReturn,
  CreateSaleReturnPayload,
  PaginatedSaleReturns,
} from '../types/saleReturn';

export async function listSales(
  filters: SaleListFilters = {},
): Promise<PaginatedSales> {
  const params: Record<string, unknown> = {};
  if (filters.customerId) params.customer_id = filters.customerId;
  if (filters.status) params.status = filters.status;
  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;
  if (filters.q?.trim()) params.q = filters.q.trim();
  if (filters.skip) params.skip = filters.skip;
  if (filters.limit) params.limit = filters.limit;
  const { data } = await api.get<PaginatedSales>('/sales', { params });
  return data;
}

export async function getSale(id: string): Promise<ApiSaleDetail> {
  const { data } = await api.get<ApiSaleDetail>(`/sales/${id}`);
  return data;
}

export async function createSale(
  payload: CreateSalePayload,
): Promise<ApiSaleDetail> {
  const { data } = await api.post<ApiSaleDetail>('/sales', payload);
  return data;
}

export async function updateSale(
  id: string,
  payload: {
    customer_id?: string | null;
    payment_method?: string;
    amount_paid?: number;
    notes?: string | null;
    discount?: number;
    tax?: number;
  },
): Promise<ApiSaleDetail> {
  const { data } = await api.patch<ApiSaleDetail>(`/sales/${id}`, payload);
  return data;
}

export async function cancelSale(id: string): Promise<void> {
  await api.delete(`/sales/${id}`);
}

export async function confirmSale(id: string): Promise<ApiSaleDetail> {
  const { data } = await api.post<ApiSaleDetail>(`/sales/${id}/confirm`);
  return data;
}

export async function createSaleReturn(
  saleId: string,
  payload: CreateSaleReturnPayload,
): Promise<ApiSaleReturn> {
  const { data } = await api.post<ApiSaleReturn>(
    `/sales/${saleId}/returns`,
    payload,
  );
  return data;
}

export async function listSaleReturns(
  saleId: string,
  skip = 0,
  limit = 50,
): Promise<PaginatedSaleReturns> {
  const { data } = await api.get<PaginatedSaleReturns>(
    `/sales/${saleId}/returns`,
    { params: { skip, limit } },
  );
  return data;
}

export async function getSaleReturn(returnId: string): Promise<ApiSaleReturn> {
  const { data } = await api.get<ApiSaleReturn>(`/sales/returns/${returnId}`);
  return data;
}

export async function cancelSaleReturn(returnId: string): Promise<ApiSaleReturn> {
  const { data } = await api.delete<ApiSaleReturn>(
    `/sales/returns/${returnId}`,
  );
  return data;
}
