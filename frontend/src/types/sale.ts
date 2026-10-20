import type { Paginated } from './catalog';

export type SaleStatus = 'DRAFT' | 'CONFIRMED' | 'CANCELLED';

export type SalePaymentMethod = 'CASH' | 'CARD' | 'TRANSFER' | 'CREDIT';

export interface ApiSaleCustomer {
  id: string;
  name: string;
}

export interface ApiSaleItem {
  id: string;
  sale_id: string;
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
  created_at: string;
}

export interface ApiSale {
  id: string;
  sale_number: string;
  status: SaleStatus;
  customer_id: string | null;
  customer: ApiSaleCustomer | null;
  payment_method: SalePaymentMethod;
  amount_paid: string;
  change_due: string;
  subtotal: string;
  discount: string;
  tax: string;
  total: string;
  notes: string | null;
  created_by: string;
  created_by_username: string | null;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
}

export interface ApiSaleDetail extends ApiSale {
  items: ApiSaleItem[];
}

export type PaginatedSales = Paginated<ApiSale>;

export interface SaleListFilters {
  customerId?: string | null;
  status?: SaleStatus | '' | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  q?: string | null;
  skip?: number;
  limit?: number;
}

export interface SaleItemPayload {
  product_id: string;
  quantity: number;
  unit_price?: number;
  discount?: number;
  tax?: number;
  tax_rate?: number;
  tax_name?: string;
}

export interface CreateSalePayload {
  customer_id?: string | null;
  payment_method: SalePaymentMethod;
  amount_paid?: number;
  notes?: string | null;
  discount?: number;
  tax?: number;
  items: SaleItemPayload[];
}

const STATUS_LABELS: Record<SaleStatus, string> = {
  DRAFT: 'Borrador',
  CONFIRMED: 'Confirmada',
  CANCELLED: 'Cancelada',
};

export function saleStatusLabel(status: SaleStatus): string {
  return STATUS_LABELS[status] ?? status;
}

const SALE_PAYMENT_METHOD_LABELS: Record<SalePaymentMethod, string> = {
  CASH: 'Efectivo',
  CARD: 'Tarjeta',
  TRANSFER: 'Transferencia',
  CREDIT: 'Crédito',
};

export function salePaymentMethodLabel(method: SalePaymentMethod): string {
  return SALE_PAYMENT_METHOD_LABELS[method] ?? method;
}
