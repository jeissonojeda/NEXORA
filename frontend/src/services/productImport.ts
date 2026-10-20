import api from './api';
import type {
  ImportBatchListResponse,
  ImportConfirmResponse,
  ImportEntitiesResponse,
  ImportPreviewResponse,
  ImportRowOverride,
} from '../types/productImport';

function buildForm(
  file: File,
  overrides?: ImportRowOverride[],
): FormData {
  const form = new FormData();
  form.append('file', file);
  // No fijar Content-Type: el navegador debe añadir el boundary del multipart.
  if (overrides && overrides.length > 0) {
    form.append('overrides', JSON.stringify(overrides));
  }
  return form;
}

export async function downloadImportTemplate(): Promise<Blob> {
  const { data } = await api.get('/products/import/template', {
    responseType: 'blob',
  });
  return data;
}

export async function listImportEntities(): Promise<ImportEntitiesResponse> {
  const { data } = await api.get<ImportEntitiesResponse>(
    '/products/import/entities',
  );
  return data;
}

export async function previewImport(
  file: File,
  overrides?: ImportRowOverride[],
): Promise<ImportPreviewResponse> {
  const { data } = await api.post<ImportPreviewResponse>(
    '/products/import/preview',
    buildForm(file, overrides),
  );
  return data;
}

export async function confirmImport(
  file: File,
  duplicatePolicy: 'SKIP_NEW' | 'UPDATE_EXISTING' = 'SKIP_NEW',
  overrides?: ImportRowOverride[],
): Promise<ImportConfirmResponse> {
  const form = buildForm(file, overrides);
  form.append('duplicate_policy', duplicatePolicy);
  const { data } = await api.post<ImportConfirmResponse>(
    '/products/import/confirm',
    form,
  );
  return data;
}

export async function listImportBatches(
  skip = 0,
  limit = 50,
): Promise<ImportBatchListResponse> {
  const { data } = await api.get<ImportBatchListResponse>('/products/import/batches', {
    params: { skip, limit },
  });
  return data;
}

export async function downloadImportErrors(batchId: string): Promise<Blob> {
  const { data } = await api.get(`/products/import/batches/${batchId}/errors`, {
    responseType: 'blob',
  });
  return data;
}
