export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  CATEGORIES: '/categorias',
  SUPPLIERS: '/proveedores',
  PRODUCTS: '/productos',
  INVENTORY: '/inventario',
  PURCHASES: '/purchases',
  CUSTOMERS: '/clientes',
  RECEIVABLES: '/cuentas-por-cobrar',
  SALES: '/ventas',
  POS: '/pos',
  CASH: '/caja',
  REPORTS: '/reportes',
  AI: '/ia',
} as const;

export type RoutePath = (typeof ROUTES)[keyof typeof ROUTES];
