import api from './api';
import type {
  ApiReportData,
  ReportExportFormat,
  ReportType,
} from '../types/report';

export type ReportFilters = Record<
  string,
  string | number | null | undefined
>;

export async function fetchReport(
  reportType: ReportType,
  filters: ReportFilters = {},
): Promise<ApiReportData> {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value),
  );
  const { data } = await api.get<ApiReportData>(`/reports/${reportType}`, {
    params,
  });
  return data;
}

function parseFilename(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      /* ignore malformed encoding */
    }
  }
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] ?? fallback;
}

export async function downloadReportExport(
  reportType: ReportType,
  format: ReportExportFormat,
  filters: ReportFilters = {},
): Promise<void> {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value),
  );
  const response = await api.get(`/reports/${reportType}/export`, {
    params: { ...params, format },
    responseType: 'blob',
  });
  const extension = format === 'pdf' ? 'pdf' : 'xlsx';
  const filename = parseFilename(
    response.headers['content-disposition'] ?? null,
    `reporte-${reportType}.${extension}`,
  );
  const url = URL.createObjectURL(response.data as Blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
