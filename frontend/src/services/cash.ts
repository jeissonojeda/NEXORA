import api from './api';
import type {
  ApiCashMovement,
  ApiCashRegisterDetail,
  CashMovementType,
  PaginatedCashMovements,
  PaginatedCashRegisters,
  RegisterListFilters,
} from '../types/cash';

export async function getCurrentRegister(): Promise<ApiCashRegisterDetail | null> {
  const { data } = await api.get<ApiCashRegisterDetail | null>(
    '/cash/registers/current',
  );
  return data;
}

export async function listRegisters(
  filters: RegisterListFilters = {},
): Promise<PaginatedCashRegisters> {
  const params: Record<string, unknown> = {};
  if (filters.status) params.status = filters.status;
  if (filters.userId) params.user_id = filters.userId;
  if (filters.dateFrom) params.date_from = filters.dateFrom;
  if (filters.dateTo) params.date_to = filters.dateTo;
  if (filters.skip) params.skip = filters.skip;
  if (filters.limit) params.limit = filters.limit;
  const { data } = await api.get<PaginatedCashRegisters>('/cash/registers', {
    params,
  });
  return data;
}

export async function getRegister(
  id: string,
): Promise<ApiCashRegisterDetail> {
  const { data } = await api.get<ApiCashRegisterDetail>(
    `/cash/registers/${id}`,
  );
  return data;
}

export async function openRegister(payload: {
  opening_amount: number;
  notes?: string | null;
}): Promise<ApiCashRegisterDetail> {
  const { data } = await api.post<ApiCashRegisterDetail>(
    '/cash/registers/open',
    payload,
  );
  return data;
}

export async function closeRegister(
  id: string,
  counted_amount: number,
): Promise<ApiCashRegisterDetail> {
  const { data } = await api.post<ApiCashRegisterDetail>(
    `/cash/registers/${id}/close`,
    { counted_amount },
  );
  return data;
}

export async function listMovements(
  registerId: string,
  filters: {
    movementType?: CashMovementType | '' | null;
    skip?: number;
    limit?: number;
  } = {},
): Promise<PaginatedCashMovements> {
  const params: Record<string, unknown> = {};
  if (filters.movementType) params.movement_type = filters.movementType;
  if (filters.skip) params.skip = filters.skip;
  if (filters.limit) params.limit = filters.limit;
  const { data } = await api.get<PaginatedCashMovements>(
    `/cash/registers/${registerId}/movements`,
    { params },
  );
  return data;
}

export async function createManualMovement(payload: {
  movement_type: 'CASH_IN' | 'CASH_OUT';
  amount: number;
  description: string;
}): Promise<ApiCashMovement> {
  const { data } = await api.post<ApiCashMovement>('/cash/movements', payload);
  return data;
}
