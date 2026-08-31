import api from './api';
import type {
  AiActionConfirmResponse,
  AiActionPreviewResponse,
  AiChatResponse,
  AiHealthResponse,
  AiHistoryResponse,
  AiInvoiceScanResponse,
  AiToolsResponse,
} from '../types/ai';

export async function chatAi(message: string): Promise<AiChatResponse> {
  const { data } = await api.post<AiChatResponse>('/ai/chat', { message });
  return data;
}

export async function scanInvoice(
  file: File,
): Promise<AiInvoiceScanResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<AiInvoiceScanResponse>('/ai/invoice/scan', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function previewAction(
  actionName: string,
  args: Record<string, unknown>,
  idempotencyKey?: string,
): Promise<AiActionPreviewResponse> {
  const { data } = await api.post<AiActionPreviewResponse>('/ai/action/preview', {
    action_name: actionName,
    args,
    idempotency_key: idempotencyKey,
  });
  return data;
}

export async function confirmAction(
  actionName: string,
  args: Record<string, unknown>,
  idempotencyKey: string,
): Promise<AiActionConfirmResponse> {
  const { data } = await api.post<AiActionConfirmResponse>('/ai/action/confirm', {
    action_name: actionName,
    args,
    idempotency_key: idempotencyKey,
  });
  return data;
}

export async function getAiHistory(
  limit = 50,
  skip = 0,
): Promise<AiHistoryResponse> {
  const { data } = await api.get<AiHistoryResponse>('/ai/history', {
    params: { limit, skip },
  });
  return data;
}

export async function getAiHealth(): Promise<AiHealthResponse> {
  const { data } = await api.get<AiHealthResponse>('/ai/health');
  return data;
}

export async function getAiTools(): Promise<AiToolsResponse> {
  const { data } = await api.get<AiToolsResponse>('/ai/tools');
  return data;
}
