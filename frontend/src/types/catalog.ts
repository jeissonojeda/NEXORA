export interface ApiCategory {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiSupplierBrief {
  id: string;
  name: string;
}

export interface ApiProduct {
  id: string;
  name: string;
  barcode: string | null;
  description: string | null;
  purchase_price: string;
  sale_price: string;
  category: { id: string; name: string };
  supplier: ApiSupplierBrief | null;
  stock: number;
  minimum_stock: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
}

export interface Movement {
  id: string;
  product_id: string;
  movement_type: 'ENTRY' | 'EXIT' | 'ADJUSTMENT' | 'RETURN';
  quantity: number;
  previous_stock: number;
  new_stock: number;
  reason: string | null;
  reference_id: string | null;
  created_by: string;
  created_by_username: string | null;
  created_at: string;
}

export interface StockOperationPayload {
  product_id: string;
  quantity: number;
  reason?: string | null;
  reference_id?: string | null;
}

export interface AdjustmentPayload {
  product_id: string;
  new_stock: number;
  reason: string;
}

export interface ProductFormValues {
  name: string;
  barcode: string;
  description: string;
  purchase_price: string;
  sale_price: string;
  category_id: string;
  supplier_id: string;
  minimum_stock: string;
}

export interface CategoryFormValues {
  name: string;
  description: string;
}

const MOVEMENT_LABELS: Record<Movement['movement_type'], string> = {
  ENTRY: 'Entrada',
  EXIT: 'Salida',
  ADJUSTMENT: 'Ajuste',
  RETURN: 'Devolución',
};

export function movementLabel(type: Movement['movement_type']): string {
  return MOVEMENT_LABELS[type] ?? type;
}
