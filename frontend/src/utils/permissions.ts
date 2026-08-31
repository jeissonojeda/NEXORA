import type { AuthUser } from '../types/auth';

/**
 * Espejo de `ROLE_PERMISSIONS` del backend (app/core/rbac.py).
 * Mantener en sincronía: aquí solo se usa para decidir qué se muestra
 * en la UI; el backend siempre valida la autorización real.
 */
const ROLE_PERMISSIONS: Record<string, readonly string[]> = {
  ADMIN: ['*'],
  CASHIER: [
    'sales.read',
    'sales.create',
    'sales.update',
    'sales.confirm',
    'sales.cancel',
    'customers.read',
    'customers.create',
    'customers.update',
    'cash.read',
    'cash.open',
    'cash.close',
    'cash.movements',
    'products.read',
    'categories.read',
    'inventory.read',
    'suppliers.read',
    'purchases.read',
    'receivables.read',
    'receivables.payment',
    'ai.read',
    'ai.analyze',
  ],
  INVENTORY_MANAGER: [
    'products.read',
    'products.create',
    'products.update',
    'products.delete',
    'categories.read',
    'categories.create',
    'categories.update',
    'categories.delete',
    'inventory.read',
    'inventory.create',
    'inventory.update',
    'suppliers.read',
    'suppliers.create',
    'suppliers.update',
    'suppliers.delete',
    'purchases.read',
    'purchases.create',
    'purchases.update',
    'purchases.confirm',
    'purchases.cancel',
    'sales.read',
    'customers.read',
    'customers.create',
    'customers.update',
    'reports.read',
    'reports.export',
    'ai.read',
    'ai.analyze',
    'ai.invoice',
    'ai.inventory',
    'ai.purchase',
    'ai.execute',
  ],
};

function grants(required: string, granted: string): boolean {
  if (granted === '*') {
    return true;
  }
  if (granted === required) {
    return true;
  }
  if (granted.endsWith('.*')) {
    return required.startsWith(granted.slice(0, -1));
  }
  return false;
}

export function userHasPermission(
  user: AuthUser | null | undefined,
  permission: string,
): boolean {
  if (!user) {
    return false;
  }
  return user.roles.some((role) =>
    (ROLE_PERMISSIONS[role.name] ?? []).some((granted) =>
      grants(permission, granted),
    ),
  );
}

export function isAdmin(user: AuthUser | null | undefined): boolean {
  return user?.roles.some((role) => role.name === 'ADMIN') ?? false;
}