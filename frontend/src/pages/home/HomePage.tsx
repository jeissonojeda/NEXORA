import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useHealth } from '../../hooks/useHealth';
import { useDashboard } from '../../hooks/useDashboard';
import { formatCurrency, formatDateTime } from '../../utils/format';
import { userHasPermission } from '../../utils/permissions';
import { salePaymentMethodLabel } from '../../types/sale';
import { AI_ANALYSIS_TYPES } from '../../types/ai';
import type { AIAnalysisType } from '../../types/ai';
import { ROUTES } from '../../routes';
import PageHeader from '../../components/ui/PageHeader';
import KpiCard from '../../components/ui/KpiCard';
import ErrorAlert from '../../components/ui/ErrorAlert';
import EmptyState from '../../components/ui/EmptyState';
import LoadingState from '../../components/ui/LoadingState';
import Badge from '../../components/ui/Badge';
import Icon from '../../components/ui/Icon';

function greeting(): { text: string; icon: string } {
  const hour = new Date().getHours();
  if (hour < 12) return { text: 'Buenos días', icon: 'sun' };
  if (hour < 19) return { text: 'Buenas tardes', icon: 'sun' };
  return { text: 'Buenas noches', icon: 'moon' };
}

function confidenceTone(score: number): 'green' | 'amber' | 'red' {
  if (score >= 80) return 'green';
  if (score >= 60) return 'amber';
  return 'red';
}

interface SectionCardProps {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}

function SectionCard({ title, action, children }: SectionCardProps) {
  return (
    <div className="nx-card flex flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 className="text-sm font-bold text-foreground">{title}</h2>
        {action}
      </div>
      <div className="flex-1 p-5">{children}</div>
    </div>
  );
}

function HomePage() {
  const { user } = useAuth();
  const { health } = useHealth();
  const { data, loading, error, reload } = useDashboard(user);

  const today = new Date().toLocaleDateString('es-CR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
  const name = user ? user.first_name || user.username || '' : '';
  const greet = greeting();
  const maxWeek = Math.max(...data.salesWeek.map((day) => day.total), 1);

  const canSeeSales = userHasPermission(user, 'sales.read');
  const canSeeProducts = userHasPermission(user, 'products.read');
  const canSeeCustomers = userHasPermission(user, 'customers.read');
  const canSeeReceivables = userHasPermission(user, 'receivables.read');
  const canSeeCash = userHasPermission(user, 'cash.read');
  const canSeeAi = userHasPermission(user, 'ai.read');

  const kpis = [
    canSeeSales && {
      label: 'Ventas hoy',
      value: loading ? '…' : formatCurrency(data.salesTodayTotal),
      icon: 'receipt' as const,
      tone: 'blue' as const,
      sub: loading
        ? undefined
        : `${data.salesTodayCount} ${data.salesTodayCount === 1 ? 'venta' : 'ventas'} · promedio ${formatCurrency(data.salesTodayAvg)}`,
    },
    canSeeProducts && {
      label: 'Productos',
      value: loading ? '…' : data.productsTotal.toLocaleString('es-CR'),
      icon: 'package' as const,
      tone: 'purple' as const,
      sub: loading
        ? undefined
        : `${data.lowStockCount} con stock bajo`,
    },
    canSeeCustomers && {
      label: 'Clientes',
      value: loading ? '…' : data.customersTotal.toLocaleString('es-CR'),
      icon: 'users' as const,
      tone: 'green' as const,
    },
    canSeeReceivables && {
      label: 'Cuentas por cobrar',
      value: loading ? '…' : formatCurrency(data.receivableBalance),
      icon: 'banknote' as const,
      tone: (data.receivableBalance > 0 ? 'amber' : 'gray') as 'amber' | 'gray',
      sub: loading
        ? undefined
        : `${data.receivableOpenCount} ${data.receivableOpenCount === 1 ? 'cuenta abierta' : 'cuentas abiertas'}`,
    },
    canSeeCash && {
      label: 'Caja (efectivo esperado)',
      value: loading
        ? '…'
        : data.currentRegister
          ? formatCurrency(data.currentRegister.summary.expected_cash)
          : 'Sin caja',
      icon: 'wallet' as const,
      tone: (data.currentRegister?.status === 'OPEN' ? 'green' : 'gray') as 'green' | 'gray',
      sub: loading
        ? undefined
        : data.currentRegister
          ? data.currentRegister.status === 'OPEN'
            ? 'Caja abierta'
            : 'Caja cerrada'
          : 'No hay caja abierta',
    },
  ].filter(Boolean) as { label: string; value: string; icon: 'receipt' | 'package' | 'users' | 'banknote' | 'wallet'; tone: 'blue' | 'purple' | 'green' | 'amber' | 'gray'; sub?: string }[];

  return (
    <div className="animate-fade-in space-y-6">
      <PageHeader
        title={`${greet.text}${name ? `, ${name}` : ''}`}
        subtitle={today}
        actions={
          health && (
            <span className="nx-badge nx-badge-green">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              {health.status === 'healthy' ? 'Sistema operativo' : 'Sistema degradado'}
            </span>
          )
        }
      />

      {error && (
        <div className="space-y-2">
          <ErrorAlert message={error} onRetry={reload} />
        </div>
      )}

      {kpis.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {kpis.map((kpi) => (
            <KpiCard
              key={kpi.label}
              label={kpi.label}
              value={kpi.value}
              icon={kpi.icon}
              tone={kpi.tone}
              sub={kpi.sub}
              loading={loading && kpi.value === '…'}
            />
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {canSeeSales && (
          <SectionCard
            title="Ventas · últimos 7 días"
            action={
              <Link to={ROUTES.SALES} className="nx-link flex items-center gap-1 text-xs">
                Ver ventas
                <Icon name="chevron-right" size={14} />
              </Link>
            }
          >
            {loading ? (
              <LoadingState rows={3} />
            ) : data.salesWeek.length === 0 ? (
              <EmptyState title="Sin ventas confirmadas en la semana" hint="Registra una venta desde el punto de venta." icon="bag" />
            ) : (
              <div className="flex h-44 items-end justify-between gap-2">
                {data.salesWeek.map((day) => (
                  <div key={day.key} className="flex flex-1 flex-col items-center gap-1.5">
                    <span className="text-[10px] font-semibold text-faint">
                      {formatCurrency(day.total)}
                    </span>
                    <div
                      title={`${day.label}: ${formatCurrency(day.total)} (${day.count} ventas)`}
                      className={`w-full max-w-12 rounded-t-lg transition-colors ${
                        day.isToday ? 'nx-brand-gradient' : 'bg-primary-soft'
                      }`}
                      style={{ height: `${Math.max(6, (day.total / maxWeek) * 100)}%` }}
                    />
                    <span
                      className={`text-[11px] ${day.isToday ? 'font-bold text-primary' : 'text-muted'}`}
                    >
                      {day.label}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        )}

        {canSeeCash && (
          <SectionCard
            title="Estado de caja"
            action={
              <Link to={ROUTES.CASH} className="nx-link flex items-center gap-1 text-xs">
                Ir a caja
                <Icon name="chevron-right" size={14} />
              </Link>
            }
          >
            {loading ? (
              <LoadingState rows={3} />
            ) : data.currentRegister ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted">Estado</span>
                  <Badge tone={data.currentRegister.status === 'OPEN' ? 'green' : 'gray'}>
                    {data.currentRegister.status === 'OPEN' ? 'Abierta' : 'Cerrada'}
                  </Badge>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-faint">
                    Efectivo esperado
                  </p>
                  <p className="text-2xl font-bold text-foreground">
                    {formatCurrency(data.currentRegister.summary.expected_cash)}
                  </p>
                </div>
                <p className="text-xs text-faint">
                  Apertura {formatCurrency(data.currentRegister.opening_amount)} ·{' '}
                  {data.currentRegister.summary.movement_count} movimientos
                </p>
                <div className="flex items-center gap-2 rounded-xl bg-primary-soft px-4 py-3 text-sm font-semibold text-primary">
                  <Icon name={data.currentRegister.status === 'OPEN' ? 'wallet' : 'clock'} size={18} />
                  {data.currentRegister.status === 'OPEN'
                    ? 'La caja se encuentra abierta'
                    : 'No hay caja abierta en este momento'}
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-3 rounded-xl bg-surface-2 px-4 py-3 text-sm text-muted">
                <Icon name="wallet" size={20} className="text-faint" />
                No hay una caja abierta actualmente.
              </div>
            )}
          </SectionCard>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {canSeeSales && (
          <SectionCard
            title="Actividad reciente"
            action={
              <Link to={ROUTES.SALES} className="nx-link flex items-center gap-1 text-xs">
                Ver todas
                <Icon name="chevron-right" size={14} />
              </Link>
            }
          >
            {loading ? (
              <LoadingState rows={4} />
            ) : data.recentSales.length === 0 ? (
              <EmptyState title="Sin ventas recientes" icon="receipt" />
            ) : (
              <ul className="divide-y divide-line">
                {data.recentSales.map((sale) => (
                  <li key={sale.id}>
                    <Link
                      to={`${ROUTES.SALES}/${sale.id}`}
                      className="flex items-center justify-between gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-surface-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">
                          {sale.sale_number}
                          <span className="ml-2 font-normal text-muted">
                            {sale.customer?.name ?? 'Cliente general'}
                          </span>
                        </p>
                        <p className="text-xs text-faint">
                          {salePaymentMethodLabel(sale.payment_method)} ·{' '}
                          {formatDateTime(sale.created_at)}
                        </p>
                      </div>
                      <span className="shrink-0 text-sm font-bold text-foreground">
                        {formatCurrency(sale.total)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        )}

        {canSeeProducts && (
          <SectionCard
            title="Stock bajo"
            action={
              <Link to={ROUTES.INVENTORY} className="nx-link flex items-center gap-1 text-xs">
                Inventario
                <Icon name="chevron-right" size={14} />
              </Link>
            }
          >
            {loading ? (
              <LoadingState rows={4} />
            ) : data.lowStock.length === 0 ? (
              <EmptyState title="Sin alertas de stock" hint="Todos los productos cubren su mínimo." icon="check-circle" />
            ) : (
              <ul className="space-y-2">
                {data.lowStock.slice(0, 6).map((product) => (
                  <li
                    key={product.id}
                    className="flex items-center justify-between rounded-lg px-2 py-1.5 transition-colors hover:bg-surface-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{product.name}</p>
                      <p className="text-xs text-faint">Mínimo {product.minimum_stock}</p>
                    </div>
                    <Badge tone="red">
                      {product.stock} uds
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        )}
      </div>

      {canSeeAi && (
        <SectionCard
          title="NEXORA IA · Análisis recientes"
          action={
            <Link to={ROUTES.AI} className="nx-link flex items-center gap-1 text-xs">
              Abrir NEXORA IA
              <Icon name="chevron-right" size={14} />
            </Link>
          }
        >
          {loading ? (
            <LoadingState rows={3} />
          ) : data.aiHistory.length === 0 ? (
            <div className="flex items-center gap-3 rounded-xl bg-primary-soft px-4 py-3 text-sm text-primary">
              <Icon name="sparkles" size={20} className="shrink-0" />
              <span>
                Ejecuta tu primer análisis en NEXORA IA para ver recomendaciones
                aquí. <Link to={ROUTES.AI} className="font-bold underline">Abrir NEXORA IA</Link>
              </span>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {data.aiHistory.map((analysis) => (
                <Link
                  key={analysis.id}
                  to={ROUTES.AI}
                  className="nx-card nx-card-hover block p-4"
                >
                  <div className="flex items-center justify-between gap-2">
                    <Badge tone="purple">
                      {AI_ANALYSIS_TYPES[analysis.analysis_type as AIAnalysisType] ??
                        analysis.analysis_type}
                    </Badge>
                    <Badge tone={confidenceTone(analysis.confidence_score)}>
                      {analysis.confidence_score}%
                    </Badge>
                  </div>
                  <p className="mt-3 line-clamp-2 text-sm text-muted">
                    {analysis.query}
                  </p>
                  <p className="mt-2 text-xs text-faint">
                    {formatDateTime(analysis.created_at)}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </SectionCard>
      )}
    </div>
  );
}

export default HomePage;