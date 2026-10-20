import api from './api';
import type {
  ApiCurrency,
  ApiSettings,
  ApiTax,
  SettingsUpdatePayload,
  TaxFormValues,
} from '../types/settings';

export async function getSettings(): Promise<ApiSettings> {
  const { data } = await api.get<ApiSettings>('/settings');
  return data;
}

export async function listCurrencies(): Promise<ApiCurrency[]> {
  const { data } = await api.get<ApiCurrency[]>('/settings/currencies');
  return data;
}

export async function updateSettings(
  payload: SettingsUpdatePayload,
): Promise<ApiSettings> {
  const { data } = await api.put<ApiSettings>('/settings', payload);
  return data;
}

export async function resetSettings(
  confirmCurrencyChange = false,
): Promise<ApiSettings> {
  const { data } = await api.post<ApiSettings>('/settings/reset', {
    confirm_currency_change: confirmCurrencyChange,
  });
  return data;
}

export async function listTaxes(
  includeInactive = false,
): Promise<ApiTax[]> {
  const { data } = await api.get<ApiTax[]>('/taxes', {
    params: { include_inactive: includeInactive },
  });
  return data;
}

export async function createTax(payload: TaxFormValues): Promise<ApiTax> {
  const { data } = await api.post<ApiTax>('/taxes', {
    name: payload.name,
    rate: payload.rate,
    description: payload.description || null,
    is_active: payload.is_active,
    is_default: payload.is_default,
  });
  return data;
}

export async function updateTax(
  id: string,
  payload: Partial<TaxFormValues>,
): Promise<ApiTax> {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) body.name = payload.name;
  if (payload.rate !== undefined) body.rate = payload.rate;
  if (payload.description !== undefined) {
    body.description = payload.description || null;
  }
  if (payload.is_active !== undefined) body.is_active = payload.is_active;
  if (payload.is_default !== undefined) body.is_default = payload.is_default;
  const { data } = await api.put<ApiTax>(`/taxes/${id}`, body);
  return data;
}

export async function deactivateTax(id: string): Promise<ApiTax> {
  const { data } = await api.delete<ApiTax>(`/taxes/${id}`);
  return data;
}

export async function uploadLogo(file: File): Promise<ApiSettings> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<ApiSettings>('/settings/logo', form);
  return data;
}

export async function deleteLogo(): Promise<ApiSettings> {
  const { data } = await api.delete<ApiSettings>('/settings/logo');
  return data;
}

export async function fetchLogoBlob(): Promise<Blob> {
  const { data } = await api.get('/settings/logo', { responseType: 'blob' });
  return data as Blob;
}
