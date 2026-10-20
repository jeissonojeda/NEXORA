export type RefundMethod = 'CASH' | 'CARD' | 'TRANSFER' | 'CREDIT';

export type ReturnCondition = 'RESALE' | 'DAMAGED' | 'REVIEW';

export type SaleReturnType = 'RETURN' | 'EXCHANGE';

export type SaleReturnStatus = 'COMPLETED' | 'CANCELLED';

export interface ApiSaleReturnItem {
  id: string;
  sale_return_id: string;
  sale_item_id: string;
  product_id: string;
  product_name: string | null;
  quantity: number;
  unit_price: string;
  discount: string;
  tax: string;
  tax_rate: string;
  tax_name: string | null;
  subtotal: string;
  total: string;
  restock: boolean;
  condition: string;
  created_at: string;
}

export interface ApiSaleReturn {
  id: string;
  return_number: string;
  sale_id: string;
  sale_number: string | null;
  exchange_sale_id: string | null;
  exchange_sale_number: string | null;
  status: SaleReturnStatus;
  return_type: SaleReturnType;
  refund_method: RefundMethod;
  reason: string | null;
  subtotal: string;
  tax: string;
  total: string;
  credit_applied: string;
  refunded_amount: string;
  created_by: string;
  created_by_username: string | null;
  created_at: string;
  items: ApiSaleReturnItem[];
}

export interface PaginatedSaleReturns {
  items: ApiSaleReturn[];
  total: number;
}

export interface SaleReturnItemPayload {
  sale_item_id: string;
  quantity: number;
  condition: ReturnCondition;
}

export interface ExchangeItemPayload {
  product_id: string;
  quantity: number;
  unit_price?: number;
  discount?: number;
  tax_rate?: number;
}

export interface CreateSaleReturnPayload {
  refund_method: RefundMethod;
  reason?: string | null;
  items: SaleReturnItemPayload[];
  idempotency_key?: string | null;
  exchange_items?: ExchangeItemPayload[];
  exchange_payment_method?: RefundMethod | null;
}

const REFUND_LABELS: Record<RefundMethod, string> = {
  CASH: 'Efectivo',
  CARD: 'Tarjeta',
  TRANSFER: 'Transferencia',
  CREDIT: 'Crédito (reduce la deuda)',
};

export function refundMethodLabel(method: RefundMethod): string {
  return REFUND_LABELS[method] ?? method;
}

const CONDITION_LABELS: Record<ReturnCondition, string> = {
  RESALE: 'Vendible (vuelve al stock)',
  DAMAGED: 'Dañado (no vuelve al stock)',
  REVIEW: 'En revisión (no vuelve al stock)',
};

export function returnConditionLabel(condition: ReturnCondition): string {
  return CONDITION_LABELS[condition] ?? condition;
}
