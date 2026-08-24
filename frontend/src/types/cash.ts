import type { Paginated } from './catalog';

export type RegisterStatus = 'OPEN' | 'CLOSED' | 'CANCELLED';

export type CashMovementType =
  | 'OPENING'
  | 'SALE'
  | 'RECEIVABLE_PAYMENT'
  | 'CASH_IN'
  | 'CASH_OUT'
  | 'ADJUSTMENT';

export type CashPaymentMethod = 'CASH' | 'CARD' | 'TRANSFER' | null;

export interface ApiCashMovement {
  id: string;
  register_id: string;
  user_id: string;
  user_username: string | null;
  movement_type: CashMovementType;
  payment_method: CashPaymentMethod;
  amount: string;
  description: string;
  reference_type: string | null;
  reference_id: string | null;
  created_at: string;
}

export interface ApiCashSummary {
  opening_total: string;
  cash_in_total: string;
  cash_out_total: string;
  cash_sales_total: string;
  card_sales_total: string;
  transfer_sales_total: string;
  credit_sales_count: number;
  cash_receivable_payments_total: string;
  card_receivable_payments_total: string;
  transfer_receivable_payments_total: string;
  movement_count: number;
  expected_cash: string;
}

export interface ApiCashRegister {
  id: string;
  user_id: string;
  user_username: string | null;
  status: RegisterStatus;
  opening_amount: string;
  notes: string | null;
  opened_at: string;
  closed_at: string | null;
  closed_by_id: string | null;
  closed_by_username: string | null;
  expected_amount: string | null;
  counted_amount: string | null;
  difference: string | null;
}

export interface ApiCashRegisterDetail extends ApiCashRegister {
  summary: ApiCashSummary;
}

export type PaginatedCashRegisters = Paginated<ApiCashRegister>;

export type PaginatedCashMovements = Paginated<ApiCashMovement>;

export interface RegisterListFilters {
  status?: RegisterStatus | '' | null;
  userId?: string | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  skip?: number;
  limit?: number;
}

const REGISTER_STATUS_LABELS: Record<RegisterStatus, string> = {
  OPEN: 'Abierta',
  CLOSED: 'Cerrada',
  CANCELLED: 'Cancelada',
};

export function registerStatusLabel(status: RegisterStatus): string {
  return REGISTER_STATUS_LABELS[status] ?? status;
}

const MOVEMENT_TYPE_LABELS: Record<CashMovementType, string> = {
  OPENING: 'Apertura',
  SALE: 'Venta',
  RECEIVABLE_PAYMENT: 'Abono de cliente',
  CASH_IN: 'Ingreso',
  CASH_OUT: 'Egreso',
  ADJUSTMENT: 'Ajuste',
};

export function movementTypeLabel(type: CashMovementType): string {
  return MOVEMENT_TYPE_LABELS[type] ?? type;
}

const PAYMENT_METHOD_LABELS: Record<string, string> = {
  CASH: 'Efectivo',
  CARD: 'Tarjeta',
  TRANSFER: 'Transferencia',
};

export function cashPaymentMethodLabel(
  method: CashPaymentMethod,
): string {
  if (!method) return '—';
  return PAYMENT_METHOD_LABELS[method] ?? method;
}
