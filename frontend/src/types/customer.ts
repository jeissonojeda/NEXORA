import type { Paginated } from './catalog';

export interface ApiCustomer {
  id: string;
  identification: string | null;
  name: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  city: string | null;
  notes: string | null;
  is_active: boolean;
  credit_enabled: boolean;
  credit_limit: string;
  current_balance: string;
  credit_available: string;
  created_at: string;
  updated_at: string;
}

export interface CustomerFormValues {
  name: string;
  identification: string;
  phone: string;
  email: string;
  address: string;
  city: string;
  notes: string;
  credit_enabled: boolean;
  credit_limit: string;
}

export interface CustomerListFilters {
  q?: string | null;
  isActive?: boolean | null;
  creditEnabled?: boolean | null;
  orderBy?: 'name' | 'created_at' | 'current_balance' | 'credit_limit';
  order?: 'asc' | 'desc';
  skip?: number;
  limit?: number;
}

export type ReceivableStatus = 'OPEN' | 'PARTIALLY_PAID' | 'PAID' | 'CANCELLED';

export type PaymentMethod = 'CASH' | 'CARD' | 'TRANSFER' | 'OTHER';

export interface ApiReceivableAccount {
  id: string;
  customer_id: string;
  customer: { id: string; name: string };
  reference_type: string;
  reference_id: string | null;
  description: string | null;
  original_amount: string;
  paid_amount: string;
  balance: string;
  due_date: string | null;
  status: ReceivableStatus;
  created_at: string;
  updated_at: string;
}

export interface ReceivableCreatePayload {
  customer_id: string;
  original_amount: string;
  description?: string | null;
  due_date?: string | null;
}

export interface ReceivablePaymentPayload {
  amount: string;
  payment_method: PaymentMethod;
  reference?: string | null;
  notes?: string | null;
  idempotency_key?: string | null;
}

export interface ApiReceivablePayment {
  id: string;
  receivable_account_id: string;
  amount: string;
  payment_method: PaymentMethod;
  reference: string | null;
  notes: string | null;
  idempotency_key: string | null;
  created_by: string;
  created_by_username: string | null;
  created_at: string;
}

export interface CreditSummary {
  credit_enabled: boolean;
  credit_limit: string;
  current_balance: string;
  credit_available: string;
}

export interface ReceivableStatusCounts {
  open_count: number;
  partially_paid_count: number;
  paid_count: number;
  cancelled_count: number;
  total_balance: string;
}

export interface ApiCustomerStatement {
  customer: ApiCustomer;
  credit: CreditSummary;
  summary: ReceivableStatusCounts;
  accounts: Paginated<ApiReceivableAccount>;
  payments: Paginated<ApiReceivablePayment>;
}

const RECEIVABLE_STATUS_LABELS: Record<ReceivableStatus, string> = {
  OPEN: 'Pendiente',
  PARTIALLY_PAID: 'Abonada',
  PAID: 'Pagada',
  CANCELLED: 'Anulada',
};

export function receivableStatusLabel(status: ReceivableStatus): string {
  return RECEIVABLE_STATUS_LABELS[status] ?? status;
}

const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  CASH: 'Efectivo',
  CARD: 'Tarjeta',
  TRANSFER: 'Transferencia',
  OTHER: 'Otro',
};

export function paymentMethodLabel(method: PaymentMethod): string {
  return PAYMENT_METHOD_LABELS[method] ?? method;
}
