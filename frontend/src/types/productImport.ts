export interface ImportRowData {
  name: string;
  barcode: string | null;
  description: string | null;
  unit: string | null;
  category_name: string | null;
  category_id: string | null;
  category_declared: boolean;
  supplier_name: string | null;
  supplier_id: string | null;
  supplier_declared: boolean;
  tax_name: string | null;
  tax_id: string | null;
  purchase_price: string | null;
  profit_percent: string | null;
  sale_price: string | null;
  stock_initial: number | null;
  minimum_stock: number | null;
  is_active: boolean | null;
  suggested_category: string | null;
  suggested_supplier: string | null;
  suggested_tax: string | null;
}

export interface ImportRow {
  row_number: number;
  status: 'VALID' | 'WARNING' | 'ERROR';
  messages: string[];
  errors: string[];
  duplicate_of: string | null;
  existing_product_id: string | null;
  data: ImportRowData;
}

/** Estado de una entidad declarada en las hojas auxiliares del archivo. */
export interface ImportEntitySummaryItem {
  name: string;
  status: 'EXISTING' | 'NEW' | 'MISSING';
  can_create: boolean;
}

export interface ImportEntitySummary {
  existing: number;
  new: number;
  total: number;
  items: ImportEntitySummaryItem[];
}

export interface ImportEntitySummaries {
  suppliers: ImportEntitySummary;
  categories: ImportEntitySummary;
  taxes: ImportEntitySummary;
}

export interface ImportPreviewResponse {
  file_name: string;
  total_rows: number;
  valid: number;
  warnings: number;
  errors: number;
  rows: ImportRow[];
  entities: ImportEntitySummaries;
  declaration_errors: string[];
}

export interface ImportConfirmResponse {
  batch_id: string;
  file_name: string;
  total_rows: number;
  created: number;
  updated: number;
  skipped: number;
  rejected: number;
  rejected_rows: ImportRow[];
  suppliers_created: number;
  categories_created: number;
}

export interface ImportBatch {
  id: string;
  file_name: string;
  row_count: number;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  rejected_count: number;
  created_by_username: string | null;
  created_at: string;
}

export interface ImportBatchListResponse {
  items: ImportBatch[];
  total: number;
  page: number;
  size: number;
}

export interface ImportEntityItem {
  id: string;
  name: string;
  is_active: boolean;
}

export interface ImportEntitiesResponse {
  categories: ImportEntityItem[];
  suppliers: ImportEntityItem[];
  taxes: ImportEntityItem[];
}

/** Corrección de referencia de una fila concreta antes de confirmar. */
export interface ImportRowOverride {
  row_number: number;
  category?: string;
  supplier?: string;
  tax?: string;
}
