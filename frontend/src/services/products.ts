import api from './api';
import type { ApiProduct, Paginated, ProductFormValues } from '../types/catalog';

export interface ProductFilters {
  q?: string | null;
  categoryId?: string | null;
  supplierId?: string | null;
  isActive?: boolean | null;
  lowStock?: boolean;
  skip?: number;
  limit?: number;
}

function buildBody(values: Partial<ProductFormValues>): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (values.name !== undefined) body.name = values.name.trim();
  if (values.barcode !== undefined) {
    body.barcode = values.barcode?.trim() ? values.barcode.trim() : null;
  }
  if (values.description !== undefined) {
    body.description = values.description?.trim() ? values.description.trim() : null;
  }
  if (values.purchase_price) body.purchase_price = Number(values.purchase_price);
  if (values.profit_percent !== undefined && values.profit_percent !== '') {
    body.profit_percent = Number(values.profit_percent);
  }
  if (values.sale_price !== undefined && values.sale_price !== '') {
    body.sale_price = Number(values.sale_price);
  }
  if (values.unit !== undefined) {
    body.unit = values.unit?.trim() ? values.unit.trim() : null;
  }
  if (values.category_id) body.category_id = values.category_id || null;
  if (values.supplier_id !== undefined) {
    body.supplier_id = values.supplier_id ? values.supplier_id : null;
  }
  if (values.tax_id !== undefined) {
    body.tax_id = values.tax_id ? values.tax_id : null;
  }
  if (values.minimum_stock) body.minimum_stock = Number(values.minimum_stock);
  return body;
}

export async function listProducts(
  filters: ProductFilters = {},
): Promise<Paginated<ApiProduct>> {
  const params: Record<string, unknown> = {};
  if (filters.q?.trim()) params.q = filters.q.trim();
  if (filters.categoryId) params.category_id = filters.categoryId;
  if (filters.supplierId) params.supplier_id = filters.supplierId;
  if (filters.isActive !== null && filters.isActive !== undefined) {
    params.is_active = filters.isActive;
  }
  if (filters.lowStock) params.low_stock = true;
  if (filters.skip) params.skip = filters.skip;
  if (filters.limit) params.limit = filters.limit;
  const { data } = await api.get<Paginated<ApiProduct>>('/products', { params });
  return data;
}

export async function getProduct(id: string): Promise<ApiProduct> {
  const { data } = await api.get<ApiProduct>(`/products/${id}`);
  return data;
}

export async function getProductByBarcode(barcode: string): Promise<ApiProduct> {
  const { data } = await api.get<ApiProduct>(
    `/products/barcode/${encodeURIComponent(barcode.trim())}`,
  );
  return data;
}

export async function createProduct(
  values: ProductFormValues & { stock?: string },
): Promise<ApiProduct> {
  const body = buildBody(values);
  if (values.stock !== undefined && values.stock !== '') {
    body.stock = Number(values.stock);
  }
  const { data } = await api.post<ApiProduct>('/products', body);
  return data;
}

export async function updateProduct(
  id: string,
  values: Partial<ProductFormValues>,
): Promise<ApiProduct> {
  const { data } = await api.patch<ApiProduct>(
    `/products/${id}`,
    buildBody(values),
  );
  return data;
}

export async function deactivateProduct(id: string): Promise<void> {
  await api.delete(`/products/${id}`);
}
