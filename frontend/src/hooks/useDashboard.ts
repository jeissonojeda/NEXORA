import { useCallback, useEffect, useRef, useState } from 'react';
import type { AuthUser } from '../types/auth';
import type { ApiSale } from '../types/sale';
import type { ApiReceivableAccount } from '../types/customer';
import { listSales } from '../services/sales';
import { listProducts } from '../services/products';
import { listLowStock } from '../services/inventory';
import { listCustomers } from '../services/customers';
import { listReceivables } from '../services/receivables';
import { getCurrentRegister } from '../services/cash';
import type { ApiCashRegisterDetail } from '../types/cash';
import type { LowStockProduct } from '../services/inventory';
import type { AIAnalysisResponse } from '../services/ai';
import { userHasPermission } from '../utils/permissions';

export interface DayTotal {
  key: string;
  label: string;
  total: number;
  count: number;
  isToday: boolean;
}

export interface DashboardData {
  salesTodayTotal: number;
  salesTodayCount: number;
  salesTodayAvg: number;
  salesWeek: DayTotal[];
  productsTotal: number;
  lowStock: LowStockProduct[];
  lowStockCount: number;
  customersTotal: number;
  receivableBalance: number;
  receivableOpenCount: number;
  currentRegister: ApiCashRegisterDetail | null;
  recentSales: ApiSale[];
  aiHistory: AIAnalysisResponse[];
}

const EMPTY_DATA: DashboardData = {
  salesTodayTotal: 0,
  salesTodayCount: 0,
  salesTodayAvg: 0,
  salesWeek: [],
  productsTotal: 0,
  lowStock: [],
  lowStockCount: 0,
  customersTotal: 0,
  receivableBalance: 0,
  receivableOpenCount: 0,
  currentRegister: null,
  recentSales: [],
  aiHistory: [],
};

interface UseDashboardResult {
  data: DashboardData;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

const MAX_PAGES = 50;
const PAGE_SIZE = 100;

async function collectSales(
  from: string,
  to: string,
): Promise<{ sales: ApiSale[]; total: number }> {
  const sales: ApiSale[] = [];
  let total = 0;
  for (let skip = 0; skip < MAX_PAGES * PAGE_SIZE; skip += PAGE_SIZE) {
    const page = await listSales({
      status: 'CONFIRMED',
      dateFrom: from,
      dateTo: to,
      skip,
      limit: PAGE_SIZE,
    });
    total = page.total;
    sales.push(...page.items);
    if (page.items.length < PAGE_SIZE) break;
  }
  return { sales, total };
}

function collectReceivables(
  status: string,
): (skip: number, limit: number) => Promise<{ items: ApiReceivableAccount[]; total: number }> {
  return (skip, limit) =>
    listReceivables({ status, skip, limit }).then((page) => ({
      items: page.items,
      total: page.total,
    }));
}

async function flatten<T>(
  fetcher: (skip: number, limit: number) => Promise<{ items: T[]; total: number }>,
): Promise<T[]> {
  const items: T[] = [];
  for (let skip = 0; skip < MAX_PAGES * PAGE_SIZE; skip += PAGE_SIZE) {
    const page = await fetcher(skip, PAGE_SIZE);
    items.push(...page.items);
    if (page.items.length < PAGE_SIZE) break;
  }
  return items;
}

function pad(value: number): string {
  return value.toString().padStart(2, '0');
}

function dayKey(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function buildWeek(from: Date): DayTotal[] {
  const days: DayTotal[] = [];
  const now = new Date();
  for (let i = 0; i < 7; i += 1) {
    const date = new Date(from.getFullYear(), from.getMonth(), from.getDate() + i);
    const today = dayKey(date) === dayKey(now);
    days.push({
      key: dayKey(date),
      label: date.toLocaleDateString('es-CR', { weekday: 'short' }),
      total: 0,
      count: 0,
      isToday: today,
    });
  }
  return days;
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
}

function endOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
}

export function useDashboard(user: AuthUser | null): UseDashboardResult {
  const [data, setData] = useState<DashboardData>(EMPTY_DATA);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const hasLoadedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function load(): Promise<void> {
      setLoading(true);
      setError(null);
      const next: DashboardData = { ...EMPTY_DATA };
      const now = new Date();
      const todayStart = startOfDay(now);
      const todayEnd = endOfDay(now);
      const weekStart = startOfDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6));
      const errors: string[] = [];

      try {
        if (userHasPermission(user, 'sales.read')) {
          try {
            const { sales } = await collectSales(weekStart.toISOString(), todayEnd.toISOString());
            next.recentSales = [...sales].sort((a, b) => {
              const aTime = new Date(a.confirmed_at ?? a.created_at).getTime();
              const bTime = new Date(b.confirmed_at ?? b.created_at).getTime();
              return bTime - aTime;
            }).slice(0, 5);
            next.salesWeek = buildWeek(weekStart);
            const todayKey = dayKey(todayStart);
            for (const sale of sales) {
              const date = new Date(sale.confirmed_at ?? sale.created_at);
              const key = dayKey(date);
              const day = next.salesWeek.find((item) => item.key === key);
              const amount = parseFloat(String(sale.total)) || 0;
              if (day) {
                day.total += amount;
                day.count += 1;
              }
              if (key === todayKey) {
                next.salesTodayTotal += amount;
                next.salesTodayCount += 1;
              }
            }
            next.salesTodayAvg =
              next.salesTodayCount > 0
                ? next.salesTodayTotal / next.salesTodayCount
                : 0;
            // Mantener todos los días de la semana para mostrar ceros cuando corresponde
            next.salesWeek = next.salesWeek.map((day) => ({ ...day }));
          } catch {
            errors.push('No se pudieron cargar las ventas del panel.');
          }
        }

        if (userHasPermission(user, 'products.read')) {
          try {
            const all = await listProducts({ limit: 1 });
            next.productsTotal = all.total;
          } catch {
            errors.push('No se pudieron cargar los productos del panel.');
          }
        }

        if (userHasPermission(user, 'inventory.read')) {
          try {
            const low = await listLowStock();
            next.lowStock = low;
            next.lowStockCount = low.length;
          } catch {
            errors.push('No se pudo cargar el inventario con stock bajo.');
          }
        }

        if (userHasPermission(user, 'customers.read')) {
          try {
            const customers = await listCustomers({ limit: 1 });
            next.customersTotal = customers.total;
          } catch {
            errors.push('No se pudieron cargar los clientes del panel.');
          }
        }

        if (userHasPermission(user, 'receivables.read')) {
          try {
            const open = await flatten(collectReceivables('OPEN'));
            const partial = await flatten(collectReceivables('PARTIALLY_PAID'));
            next.receivableOpenCount = open.length + partial.length;
            next.receivableBalance = [...open, ...partial].reduce(
              (sum, account) => sum + (parseFloat(String(account.balance)) || 0),
              0,
            );
          } catch {
            errors.push('No se pudieron cargar las cuentas por cobrar.');
          }
        }

        if (userHasPermission(user, 'cash.read')) {
          try {
            next.currentRegister = await getCurrentRegister();
          } catch {
            errors.push('No se pudo consultar el estado de caja.');
          }
        }

        if (userHasPermission(user, 'ai.read')) {
          try {
            const { getAnalysisHistory } = await import('../services/ai');
            next.aiHistory = await getAnalysisHistory(0, 3);
          } catch {
            // Historial IA opcional; no debe romper el dashboard
          }
        }

        if (!cancelled) {
          setData((prev) => {
            // Si ya hay datos cargados y solo hay errores parciales, conservar datos previos donde aplique
            if (hasLoadedRef.current && errors.length > 0) {
              return {
                ...next,
                recentSales: next.recentSales.length > 0 ? next.recentSales : prev.recentSales,
                salesWeek: next.salesWeek.length > 0 ? next.salesWeek : prev.salesWeek,
                lowStock: next.lowStock.length > 0 || errors.some((e) => e.includes('inventario')) ? next.lowStock : prev.lowStock,
                aiHistory: next.aiHistory.length > 0 ? next.aiHistory : prev.aiHistory,
              };
            }
            return next;
          });
          hasLoadedRef.current = true;
          setError(errors.length > 0 ? errors.join(' ') : null);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setError('No se pudieron cargar los indicadores del panel.');
          setLoading(false);
        }
      }
    }

    void load();

    const handleFocus = () => {
      setAttempt((value) => value + 1);
    };
    window.addEventListener('focus', handleFocus);

    return () => {
      cancelled = true;
      window.removeEventListener('focus', handleFocus);
    };
  }, [user, attempt]);

  const reload = useCallback(() => {
    setAttempt((value) => value + 1);
  }, []);

  return { data, loading, error, reload };
}
