import { useMemo, useState, type FormEvent } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useAsync, extractErrorMessage } from '../../hooks/useAsync';
import api from '../../services/api';
import {
  downloadReportExport,
  fetchReport,
  type ReportFilters,
} from '../../services/reports';
import {
  INVENTORY_STATE_LABELS,
  PAYMENT_METHOD_LABELS,
  PURCHASE_STATUS_LABELS,
  RECEIVABLE_STATUS_LABELS,
  REPORT_OPTIONS,
  type ReportColumn,
  type ReportExportFormat,
  type ReportFilterSpec,
  type ReportType,
} from '../../types/report';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import Icon from '../../components/ui/Icon';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import { formatCurrency, formatDateTime } from '../../utils/format';

const PAGE_SIZE = 20;

function formatCell(column: ReportColumn, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  switch (column.type) {
    case 'money':
      return formatCurrency(String(value));
    case 'int':
      return Number(value).toLocaleString('es-CR');
    case 'datetime':
      return formatDateTime(String(value));
    case 'date':
      return String(value);
    default:
      return String(value);
  }
}

function formatTotal(column: ReportColumn, value: unknown): string | null {
  if (value === null || value === undefined) return null;
  return formatCell(column, value);
}

interface UserOption {
  id: string;
  username: string;
}

export default function ReportsPage() {
  const { user } = useAuth();
  const canView =
    user?.roles.some((role) =>
      ['ADMIN', 'INVENTORY_MANAGER'].includes(role.name),
    ) ?? false;
  const isAdmin =
    user?.roles.some((role) => role.name === 'ADMIN') ?? false;

  const [reportKey, setReportKey] = useState<ReportType>('sales');
  const [draftFilters, setDraftFilters] = useState<ReportFilters>({});
  const [appliedFilters, setAppliedFilters] = useState<ReportFilters>({});
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState<ReportExportFormat | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const option = REPORT_OPTIONS.find((item) => item.key === reportKey)!;

  const categoriesState = useAsync<{ data: { id: string; name: string }[] }>(
    () =>
      option.filters.some((filter) => filter.kind === 'category')
        ? api.get('/categories')
        : Promise.resolve({ data: [] as { id: string; name: string }[] }),
    [reportKey],
  );

  const suppliersState = useAsync<{
    data: { items: { id: string; name: string }[] };
  }>(
    () =>
      option.filters.some((filter) => filter.kind === 'supplier')
        ? api.get('/suppliers', { params: { limit: 200 } })
        : Promise.resolve({ data: { items: [] } }),
    [reportKey],
  );

  const customersState = useAsync<{
    data: { items: { id: string; name: string }[] };
  }>(
    () =>
      option.filters.some((filter) => filter.kind === 'customer')
        ? api.get('/customers', { params: { limit: 200 } })
        : Promise.resolve({ data: { items: [] } }),
    [reportKey],
  );

  const usersState = useAsync(
    () =>
      isAdmin && option.filters.some((filter) => filter.kind === 'user')
        ? api.get<UserOption[]>('/users')
        : Promise.resolve({ data: [] as UserOption[] }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [isAdmin, reportKey],
  );

  const effectiveFilters = useMemo<ReportFilters>(() => {
    const cleaned: ReportFilters = {};
    for (const filter of option.filters) {
      const rawValue = appliedFilters[filter.param];
      if (rawValue) cleaned[filter.param] = rawValue;
    }
    return cleaned;
  }, [appliedFilters, option]);

  const reportState = useAsync(
    () =>
      fetchReport(reportKey, {
        ...effectiveFilters,
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [reportKey, effectiveFilters, page],
  );

  function handleReportChange(nextKey: ReportType) {
    setReportKey(nextKey);
    setDraftFilters({});
    setAppliedFilters({});
    setExportError(null);
    setPage(1);
  }

  function handleApplyFilters(event: FormEvent) {
    event.preventDefault();
    setAppliedFilters({ ...draftFilters });
    setPage(1);
    setExportError(null);
  }

  async function handleExport(format: ReportExportFormat) {
    setExportError(null);
    setExporting(format);
    try {
      await downloadReportExport(reportKey, format, effectiveFilters);
    } catch (err) {
      setExportError(extractErrorMessage(err));
    } finally {
      setExporting(null);
    }
  }

  if (!canView) {
    return (
      <div className="space-y-4">
        <PageHeader title="Reportes" subtitle="Indicadores y exportación de información." />
        <ErrorAlert message="No tienes permisos para consultar reportes." />
      </div>
    );
  }

  const report = reportState.data;
  const hasTotals = Boolean(report && Object.keys(report.totals).length > 0);

  function renderFilterInput(filter: ReportFilterSpec) {
    const value = draftFilters[filter.param] ?? '';
    function setValue(next: string) {
      setDraftFilters((current) => ({ ...current, [filter.param]: next }));
    }
    switch (filter.kind) {
      case 'date':
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <input
              id={`filter-${filter.param}`}
              type="datetime-local"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-input"
            />
          </div>
        );
      case 'category':
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <select
              id={`filter-${filter.param}`}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-select"
            >
              <option value="">Todas</option>
              {(categoriesState.data?.data ?? []).map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </div>
        );
      case 'supplier': {
        const suppliers = suppliersState.data?.data.items ?? [];
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <select
              id={`filter-${filter.param}`}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-select"
            >
              <option value="">Todos</option>
              {suppliers.map((supplier) => (
                <option key={supplier.id} value={supplier.id}>
                  {supplier.name}
                </option>
              ))}
            </select>
          </div>
        );
      }
      case 'customer': {
        const customers = customersState.data?.data.items ?? [];
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <select
              id={`filter-${filter.param}`}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-select"
            >
              <option value="">Todos</option>
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.name}
                </option>
              ))}
            </select>
          </div>
        );
      }
      case 'user': {
        const users = usersState.data?.data ?? [];
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <select
              id={`filter-${filter.param}`}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-select"
            >
              <option value="">Todos</option>
              {users.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.username}
                </option>
              ))}
            </select>
          </div>
        );
      }
      case 'payment_method':
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <select
              id={`filter-${filter.param}`}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-select"
            >
              <option value="">Todos</option>
              {Object.entries(PAYMENT_METHOD_LABELS).map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        );
      case 'state':
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <select
              id={`filter-${filter.param}`}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-select"
            >
              <option value="">Todos</option>
              {Object.entries(INVENTORY_STATE_LABELS).map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        );
      case 'purchase_status':
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <select
              id={`filter-${filter.param}`}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-select"
            >
              <option value="">Todos</option>
              {Object.entries(PURCHASE_STATUS_LABELS).map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        );
      case 'receivable_status':
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <select
              id={`filter-${filter.param}`}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-select"
            >
              <option value="">Todos</option>
              {Object.entries(RECEIVABLE_STATUS_LABELS).map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        );
      case 'period':
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <select
              id={`filter-${filter.param}`}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-select"
            >
              <option value="">Todo el periodo</option>
              <option value="DAY">Diario</option>
              <option value="MONTH">Mensual</option>
            </select>
          </div>
        );
      case 'q':
        return (
          <div key={filter.param}>
            <label htmlFor={`filter-${filter.param}`} className="nx-label">
              {filter.label}
            </label>
            <input
              id={`filter-${filter.param}`}
              type="text"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="nx-input"
              placeholder="Nombre o identificación…"
            />
          </div>
        );
      default:
        return null;
    }
  }

  return (
    <div className="animate-fade-in space-y-4">
      <PageHeader title="Reportes" subtitle="Indicadores comerciales e inventario con exportación." />

      <div className="nx-card p-4">
        <div className="grid gap-3 md:grid-cols-[minmax(200px,260px)_1fr_auto_auto] md:items-end">
          <div>
            <label htmlFor="report-type" className="nx-label">
              Tipo de reporte
            </label>
            <select
              id="report-type"
              value={reportKey}
              onChange={(event) =>
                handleReportChange(event.target.value as ReportType)
              }
              className="nx-select"
            >
              {REPORT_OPTIONS.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <p className="pb-2 text-sm text-muted">{option.description}</p>
          <button
            type="button"
            onClick={() => void handleExport('pdf')}
            disabled={exporting !== null || !report || report.total === 0}
            className="nx-btn nx-btn-danger"
          >
            <Icon name="printer" size={16} />
            {exporting === 'pdf' ? 'Generando…' : 'PDF'}
          </button>
          <button
            type="button"
            onClick={() => void handleExport('excel')}
            disabled={exporting !== null || !report || report.total === 0}
            className="nx-btn nx-btn-success"
          >
            <Icon name="download" size={16} />
            {exporting === 'excel' ? 'Generando…' : 'Excel'}
          </button>
        </div>

        {option.filters.length > 0 && (
          <form onSubmit={handleApplyFilters} className="mt-4 border-t border-line pt-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:items-end">
              {option.filters.map((filter) => renderFilterInput(filter))}
              <div className="flex justify-end gap-2 lg:col-span-full">
                <button
                  type="submit"
                  className="nx-btn nx-btn-primary"
                >
                  Aplicar filtros
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDraftFilters({});
                    setAppliedFilters({});
                    setPage(1);
                  }}
                  className="nx-btn nx-btn-secondary"
                >
                  Limpiar
                </button>
              </div>
            </div>
          </form>
        )}
      </div>

      {exportError && <ErrorAlert message={exportError} />}
      {reportState.error && <ErrorAlert message={reportState.error} />}

      <div className="nx-card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
          <span className="text-sm font-semibold text-foreground">
            {report ? report.title : 'Reporte'}
          </span>
          {report && (
            <span className="text-xs text-faint">
              Generado {formatDateTime(report.generated_at)} ·{' '}
              {report.total} fila(s){' '}
              {report.limit != null && report.total > report.limit
                ? `(mostrando ${report.items.length})`
                : ''}
            </span>
          )}
        </div>

        {reportState.loading ? (
          <p className="px-4 py-10 text-center text-sm text-muted">
            Cargando reporte…
          </p>
        ) : !report || report.total === 0 ? (
          <div className="p-6">
            <EmptyState
              title="Sin resultados"
              hint="Ajusta los filtros o registra movimientos para ver datos aquí."
            />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="nx-table">
                <thead>
                  <tr>
                    {report.columns.map((column) => (
                      <th
                        key={column.key}
                        className={
                          column.type === 'money' || column.type === 'int'
                            ? 'text-right'
                            : 'text-left'
                        }
                      >
                        {column.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {report.items.map((row, index) => (
                    <tr key={index} className="hover:bg-surface-2">
                      {report.columns.map((column) => (
                        <td
                          key={column.key}
                          className={`whitespace-nowrap ${
                            column.type === 'money' || column.type === 'int'
                              ? 'text-right text-muted tabular-nums'
                              : 'text-muted'
                          }`}
                        >
                          {formatCell(column, row[column.key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
                {hasTotals && (
                  <tfoot className="bg-surface-2 font-semibold text-foreground">
                    <tr>
                      {report.columns.map((column, columnIndex) => {
                        if (columnIndex === 0) {
                          return (
                            <td key={column.key} className="px-4 py-3">
                              TOTALES
                            </td>
                          );
                        }
                        const totalValue = report.totals[column.key];
                        return (
                          <td
                            key={column.key}
                            className={`px-4 py-3 ${
                              column.type === 'money' || column.type === 'int'
                                ? 'text-right tabular-nums'
                                : ''
                            }`}
                          >
                            {formatTotal(column, totalValue) ?? ''}
                          </td>
                        );
                      })}
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
            <div className="border-t border-line px-4 py-3">
              <Pagination
                page={page}
                pageSize={PAGE_SIZE}
                total={report.total}
                onChange={setPage}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}