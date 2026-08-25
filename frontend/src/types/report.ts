export type ReportType =
  | 'sales'
  | 'products-sold'
  | 'inventory'
  | 'low-stock'
  | 'purchases'
  | 'cash-registers'
  | 'customers-credit'
  | 'receivables'
  | 'utilities';

export type ReportColumnType = 'text' | 'money' | 'int' | 'datetime' | 'date';

export interface ReportColumn {
  key: string;
  label: string;
  type: ReportColumnType;
}

export interface ReportFilterApplied {
  param: string;
  label: string;
  value: string | null;
}

export interface ApiReportData {
  report_type: ReportType;
  title: string;
  generated_at: string;
  filters_applied: ReportFilterApplied[];
  columns: ReportColumn[];
  items: Record<string, unknown>[];
  skip: number;
  limit: number | null;
  total: number;
  totals: Record<string, string | number>;
}

export type ReportExportFormat = 'pdf' | 'excel';

export interface ReportFilterSpec {
  param: string;
  label: string;
  kind:
    | 'date'
    | 'category'
    | 'user'
    | 'payment_method'
    | 'state'
    | 'purchase_status'
    | 'receivable_status'
    | 'supplier'
    | 'customer'
    | 'q'
    | 'period';
}

interface ReportOption {
  key: ReportType;
  label: string;
  description: string;
  filters: ReportFilterSpec[];
}

const DATE_RANGE_FILTERS: ReportFilterSpec[] = [
  { param: 'date_from', label: 'Desde', kind: 'date' },
  { param: 'date_to', label: 'Hasta', kind: 'date' },
];

export const REPORT_OPTIONS: ReportOption[] = [
  {
    key: 'sales',
    label: 'Ventas',
    description: 'Ventas confirmadas con totales y filtros por fecha, vendedor y método de pago.',
    filters: [
      ...DATE_RANGE_FILTERS,
      { param: 'user_id', label: 'Vendedor', kind: 'user' },
      { param: 'payment_method', label: 'Método de pago', kind: 'payment_method' },
    ],
  },
  {
    key: 'products-sold',
    label: 'Productos vendidos',
    description: 'Unidades e ingresos por producto en ventas confirmadas.',
    filters: [...DATE_RANGE_FILTERS, { param: 'category_id', label: 'Categoría', kind: 'category' }],
  },
  {
    key: 'inventory',
    label: 'Inventario valorizado',
    description: 'Stock actual con valor a costo y a precio de venta.',
    filters: [
      ...DATE_RANGE_FILTERS,
      { param: 'category_id', label: 'Categoría', kind: 'category' },
      { param: 'state', label: 'Estado', kind: 'state' },
    ],
  },
  {
    key: 'low-stock',
    label: 'Stock bajo',
    description: 'Productos activos que alcanzaron o cruzaron su mínimo, ordenados por faltante.',
    filters: [...DATE_RANGE_FILTERS, { param: 'category_id', label: 'Categoría', kind: 'category' }],
  },
  {
    key: 'purchases',
    label: 'Compras',
    description: 'Compras a proveedores con estado, fechas y totales.',
    filters: [
      ...DATE_RANGE_FILTERS,
      { param: 'status', label: 'Estado', kind: 'purchase_status' },
      { param: 'supplier_id', label: 'Proveedor', kind: 'supplier' },
    ],
  },
  {
    key: 'cash-registers',
    label: 'Caja',
    description: 'Turnos de caja con montos esperados, contados y diferencias.',
    filters: [...DATE_RANGE_FILTERS, { param: 'user_id', label: 'Cajero', kind: 'user' }],
  },
  {
    key: 'customers-credit',
    label: 'Clientes con crédito',
    description: 'Saldo corriente y saldo vigente en cuentas por cobrar por cliente.',
    filters: [...DATE_RANGE_FILTERS, { param: 'q', label: 'Buscar cliente', kind: 'q' }],
  },
  {
    key: 'receivables',
    label: 'Cuentas por cobrar',
    description: 'Cuentas de clientes con pagos aplicados y saldos pendientes.',
    filters: [
      ...DATE_RANGE_FILTERS,
      { param: 'status', label: 'Estado', kind: 'receivable_status' },
      { param: 'customer_id', label: 'Cliente', kind: 'customer' },
    ],
  },
  {
    key: 'utilities',
    label: 'Utilidades',
    description: 'Ingresos, costo estimado y utilidad agrupados por día o mes (aproximado).',
    filters: [...DATE_RANGE_FILTERS, { param: 'period', label: 'Período', kind: 'period' }],
  },
];

export const PAYMENT_METHOD_LABELS: Record<string, string> = {
  CASH: 'Efectivo',
  CARD: 'Tarjeta',
  TRANSFER: 'Transferencia',
};

export const INVENTORY_STATE_LABELS: Record<string, string> = {
  active: 'Activos',
  inactive: 'Inactivos',
};

export const PURCHASE_STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Borrador',
  CONFIRMED: 'Confirmada',
  CANCELLED: 'Cancelada',
};

export const RECEIVABLE_STATUS_LABELS: Record<string, string> = {
  OPEN: 'Abierta',
  PARTIALLY_PAID: 'Parcial',
  PAID: 'Pagada',
  CANCELLED: 'Anulada',
};
