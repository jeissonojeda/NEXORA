import type { Paginated } from './catalog';

export type PurchaseStatus = 'DRAFT' | 'CONFIRMED' | 'CANCELLED';

export interface ApiPurchaseSupplier {
  id: string;
  name: string;
}

export interface ApiPurchaseItem {
  id: string;
  purchase_id: string;
  product_id: string;
  product_name: string | null;
  quantity: number;
  unit_cost: string;
  discount: string;
  tax: string;
  subtotal: string;
  total: string;
  created_at: string;
}

export interface ApiPurchase {
  id: string;
  purchase_number: string;
  status: PurchaseStatus;
  supplier_id: string;
  supplier: ApiPurchaseSupplier;
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

export interface ApiPurchaseDetail extends ApiPurchase {
  items: ApiPurchaseItem[];
}

export type PaginatedPurchases = Paginated<ApiPurchase>;

export interface PurchaseListFilters {
  supplierId?: string | null;
  status?: PurchaseStatus | '' | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  q?: string | null;
  skip?: number;
  limit?: number;
}

export interface PurchaseItemPayload {
  product_id: string;
  quantity: number;
  unit_cost: number;
  discount?: number;
  tax?: number;
}

const STATUS_LABELS: Record<PurchaseStatus, string> = {
  DRAFT: 'Borrador',
  CONFIRMED: 'Confirmada',
  CANCELLED: 'Cancelada',
};

export function purchaseStatusLabel(status: PurchaseStatus): string {
  return STATUS_LABELS[status] ?? status;
}
