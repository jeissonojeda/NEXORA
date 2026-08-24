export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  CATEGORIES: '/categorias',
  SUPPLIERS: '/proveedores',
  PRODUCTS: '/productos',
  INVENTORY: '/inventario',
  PURCHASES: '/purchases',
  CUSTOMERS: '/clientes',
} as const;

export type RoutePath = (typeof ROUTES)[keyof typeof ROUTES];
