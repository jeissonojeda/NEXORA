import api from './api';
import type {
  ApiPurchaseDetail,
  PaginatedPurchases,
  PurchaseItemPayload,
  PurchaseListFilters,
} from '../types/purchase';

export async function listPurchases(
  filters: PurchaseListFilters = {},
): Promise<PaginatedPurchases> {
  const params: Record<string, unknown> = {};
  if (filters.supplierId) params.supplier_id = filters.supplierId;
  if (filters.status) params.status = filters.status;
  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;
  if (filters.q?.trim()) params.q = filters.q.trim();
  if (filters.skip) params.skip = filters.skip;
  if (filters.limit) params.limit = filters.limit;
  const { data } = await api.get<PaginatedPurchases>('/purchases', { params });
  return data;
}

export async function getPurchase(id: string): Promise<ApiPurchaseDetail> {
  const { data } = await api.get<ApiPurchaseDetail>(`/purchases/${id}`);
  return data;
}

export async function createPurchase(payload: {
  supplier_id: string;
  notes?: string | null;
}): Promise<ApiPurchaseDetail> {
  const { data } = await api.post<ApiPurchaseDetail>('/purchases', payload);
  return data;
}

export async function updatePurchase(
  id: string,
  payload: {
    supplier_id?: string;
    notes?: string | null;
    discount?: number;
    tax?: number;
  },
): Promise<ApiPurchaseDetail> {
  const { data } = await api.patch<ApiPurchaseDetail>(
    `/purchases/${id}`,
    payload,
  );
  return data;
}

export async function cancelPurchase(id: string): Promise<void> {
  await api.delete(`/purchases/${id}`);
}

export async function confirmPurchase(id: string): Promise<ApiPurchaseDetail> {
  const { data } = await api.post<ApiPurchaseDetail>(`/purchases/${id}/confirm`);
  return data;
}

export async function addPurchaseItem(
  purchaseId: string,
  item: PurchaseItemPayload,
): Promise<ApiPurchaseDetail['items'][number]> {
  const { data } = await api.post(
    `/purchases/${purchaseId}/items`,
    item,
  );
  return data;
}

export async function updatePurchaseItem(
  purchaseId: string,
  itemId: string,
  item: Partial<Omit<PurchaseItemPayload, 'product_id'>>,
): Promise<ApiPurchaseDetail['items'][number]> {
  const { data } = await api.patch(
    `/purchases/${purchaseId}/items/${itemId}`,
    item,
  );
  return data;
}

export async function removePurchaseItem(
  purchaseId: string,
  itemId: string,
): Promise<void> {
  await api.delete(`/purchases/${purchaseId}/items/${itemId}`);
}
