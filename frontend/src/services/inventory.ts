import api from './api';
import type {
  AdjustmentPayload,
  Movement,
  Paginated,
  StockOperationPayload,
} from '../types/catalog';

export interface MovementFilters {
  productId?: string | null;
  movementType?: string | null;
  createdBy?: string | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  skip?: number;
  limit?: number;
}

async function postOperation(
  path: 'entries' | 'exits' | 'returns',
  payload: StockOperationPayload,
): Promise<Movement> {
  const body: Record<string, unknown> = {
    product_id: payload.product_id,
    quantity: payload.quantity,
  };
  if (payload.reason?.trim()) body.reason = payload.reason.trim();
  if (payload.reference_id?.trim()) body.reference_id = payload.reference_id.trim();
  const { data } = await api.post<Movement>(`/inventory/${path}`, body);
  return data;
}

export const registerEntry = (payload: StockOperationPayload) =>
  postOperation('entries', payload);

export const registerExit = (payload: StockOperationPayload) =>
  postOperation('exits', payload);

export const registerReturn = (payload: StockOperationPayload) =>
  postOperation('returns', payload);

export async function registerAdjustment(
  payload: AdjustmentPayload,
): Promise<Movement> {
  const { data } = await api.post<Movement>('/inventory/adjustments', {
    product_id: payload.product_id,
    new_stock: payload.new_stock,
    reason: payload.reason.trim(),
  });
  return data;
}

export async function listMovements(
  filters: MovementFilters = {},
): Promise<Paginated<Movement>> {
  const params: Record<string, unknown> = {};
  if (filters.productId) params.product_id = filters.productId;
  if (filters.movementType) params.movement_type = filters.movementType;
  if (filters.createdBy) params.created_by = filters.createdBy;
  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;
  if (filters.skip) params.skip = filters.skip;
  if (filters.limit) params.limit = filters.limit;
  const { data } = await api.get<Paginated<Movement>>('/inventory/movements', {
    params,
  });
  return data;
}

export async function getMovement(id: string): Promise<Movement> {
  const { data } = await api.get<Movement>(`/inventory/movements/${id}`);
  return data;
}

export interface LowStockProduct {
  id: string;
  name: string;
  barcode: string | null;
  stock: number;
  minimum_stock: number;
  category: { name: string };
}

export async function listLowStock(): Promise<LowStockProduct[]> {
  const { data } = await api.get<LowStockProduct[]>('/inventory/low-stock');
  return data;
}
