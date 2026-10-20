export interface AIAnalysis {
  id: string;
  user_id: string;
  analysis_type: string;
  product_id?: string;
  category_id?: string;
  query: string;
  response: string;
  confidence_score: number;
  recommendations?: string[];
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AITrend {
  product_id?: string;
  category_id?: string;
  trend_direction: 'up' | 'down' | 'stable';
  trend_strength: number;
  forecast?: Array<{ date: string; predicted_quantity: number }>;
  insights: string[];
  recommendations: string[];
  confidence_score: number;
}

export interface AIBatchAnalysis {
  analyses: AIAnalysis[];
  summary: string;
  total_products: number;
  products_needing_attention: number;
  estimated_stockout_risk: number;
}

export type AIAnalysisType = 'reorder' | 'trend' | 'anomaly' | 'recommendation';

export const AI_ANALYSIS_TYPES: Record<AIAnalysisType, string> = {
  reorder: 'Reorden de Productos',
  trend: 'Análisis de Tendencias',
  anomaly: 'Detección de Anomalías',
  recommendation: 'Recomendaciones'
};

export function getConfidenceColor(score: number): string {
  if (score >= 80) return 'text-green-600 bg-green-50';
  if (score >= 60) return 'text-yellow-600 bg-yellow-50';
  return 'text-red-600 bg-red-50';
}

export function getTrendIcon(direction: string): string {
  switch (direction) {
    case 'up': return '📈';
    case 'down': return '📉';
    default: return '➡️';
  }
}

// ----------------------------------------------------------------------
// NEXORA AI Operativo (Fase 12): chat con tools, acciones y escaneo de
// facturas vía Gemini. La IA propone acciones; el backend nunca ejecuta
// escrituras sin confirmación del usuario.
// ----------------------------------------------------------------------

export interface AiToolResult {
  name: string;
  output?: unknown;
  error?: string | null;
}

export interface AiActionProposal {
  action_name: string;
  action_type: string;
  args: Record<string, unknown>;
  permission: string;
}

export interface AiChatMessage {
  role: 'user' | 'assistant';
  text: string;
}

export interface AiChatResponse {
  message: string;
  tool_results: AiToolResult[];
  action_proposals: AiActionProposal[];
  model_used?: string | null;
  tokens_used?: number | null;
  duration_ms?: number | null;
}

export interface AiInvoiceItem {
  product_name: string;
  quantity: string;
  unit_price: string;
  total: string;
}

export interface AiSupplierMatch {
  id: string;
  name: string;
  confidence: number;
}

export interface AiProductMatch {
  id: string;
  name: string;
  barcode?: string | null;
  confidence: number;
}

export interface AiInvoiceScanResponse {
  scan_id: string;
  file_name?: string | null;
  supplier_name?: string | null;
  invoice_number?: string | null;
  total?: string | null;
  items: AiInvoiceItem[];
  supplier_matches: AiSupplierMatch[];
  product_matches: AiProductMatch[];
  duplicate: boolean;
  duplicate_of?: string | null;
  raw_text?: string | null;
}

export interface AiActionPreviewResponse {
  action_type: string;
  action_name: string;
  display: Record<string, unknown>;
  args: Record<string, unknown>;
  requires_confirmation: boolean;
  idempotency_key?: string | null;
}

export interface AiActionConfirmResponse {
  status: string;
  action_type: string;
  action_name: string;
  result: Record<string, unknown>;
  idempotency_key: string;
  reference_id?: string | null;
  replayed?: boolean;
}

export interface AiHistoryEntry {
  id: string;
  action_type: string;
  action_name: string;
  status: string;
  payload_json?: string | null;
  result_json?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  idempotency_key?: string | null;
  created_at: string;
}

export interface AiHistoryResponse {
  items: AiHistoryEntry[];
  total: number;
}

export interface AiHealthResponse {
  available: boolean;
  model?: string | null;
}

export interface AiToolsResponse {
  read_tools: Array<Record<string, unknown>>;
  action_tools: Array<Record<string, unknown>>;
}

export const AI_ACTION_LABELS: Record<string, string> = {
  create_purchase: 'Crear compra',
  adjust_inventory: 'Ajustar inventario',
  create_product: 'Crear producto',
  create_supplier: 'Crear proveedor',
  register_payment: 'Registrar pago',
};

export const AI_ACTION_TYPE_LABELS: Record<string, string> = {
  purchase: 'Compra',
  inventory: 'Inventario',
  product: 'Producto',
  supplier: 'Proveedor',
  payment: 'Pago',
};

export const AI_HISTORY_STATUS_TONES: Record<string, 'green' | 'red' | 'amber' | 'gray' | 'blue' | 'purple'> = {
  CONFIRMED: 'green',
  FAILED: 'red',
  REJECTED: 'amber',
  PREVIEW: 'blue',
};
