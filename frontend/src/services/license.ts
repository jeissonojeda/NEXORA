import api from './api';
import type { LicenseStatus } from '../types/license';

export async function getLicenseStatus(): Promise<LicenseStatus> {
  const { data } = await api.get<LicenseStatus>('/license/status');
  return data;
}

export async function activateLicense(licenseKey: string): Promise<LicenseStatus> {
  const { data } = await api.post<LicenseStatus>('/license/activate', {
    license_key: licenseKey,
  });
  return data;
}

export async function createManualRequest(licenseKey: string): Promise<string> {
  const { data } = await api.post<{ request_code: string }>('/license/manual-request', {
    license_key: licenseKey,
  });
  return data.request_code;
}

export async function importManualResponse(responseCode: string): Promise<LicenseStatus> {
  const { data } = await api.post<LicenseStatus>('/license/manual-import', {
    response_code: responseCode,
  });
  return data;
}
