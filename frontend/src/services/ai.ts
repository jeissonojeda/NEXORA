import api from './api';

export interface AIAnalysisRequest {
  analysis_type: string;
  query: string;
  product_id?: string;
  category_id?: string;
  time_range_days?: number;
  include_recommendations?: boolean;
}

export interface AIAnalysisResponse {
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

export interface AITrendRequest {
  product_id?: string;
  category_id?: string;
  period_days?: number;
  include_forecast?: boolean;
}

export interface AITrendResponse {
  product_id?: string;
  category_id?: string;
  trend_direction: string;
  trend_strength: number;
  forecast?: Array<{ date: string; predicted_quantity: number }>;
  insights: string[];
  recommendations: string[];
  confidence_score: number;
}

export interface AIBatchAnalysisRequest {
  product_ids: string[];
  analysis_type?: string;
  include_cross_selling?: boolean;
}

export interface AIBatchAnalysisResponse {
  analyses: AIAnalysisResponse[];
  summary: string;
  total_products: number;
  products_needing_attention: number;
  estimated_stockout_risk: number;
}

export async function performAnalysis(request: AIAnalysisRequest): Promise<AIAnalysisResponse> {
  const response = await api.post('/ai/analyze', request);
  return response.data;
}

export async function getTrends(request: AITrendRequest): Promise<AITrendResponse> {
  const params = new URLSearchParams();
  if (request.product_id) params.append('product_id', request.product_id);
  if (request.category_id) params.append('category_id', request.category_id);
  if (request.period_days) params.append('period_days', request.period_days.toString());
  if (request.include_forecast !== undefined) {
    params.append('include_forecast', request.include_forecast.toString());
  }
  
  const response = await api.get(`/ai/trends?${params.toString()}`);
  return response.data;
}

export async function batchAnalyze(request: AIBatchAnalysisRequest): Promise<AIBatchAnalysisResponse> {
  const response = await api.post('/ai/batch-analyze', request);
  return response.data;
}

export async function getAnalysisHistory(skip = 0, limit = 50): Promise<AIAnalysisResponse[]> {
  const response = await api.get(`/ai/analysis?skip=${skip}&limit=${limit}`);
  return response.data;
}

export async function getAnalysisById(analysisId: string): Promise<AIAnalysisResponse> {
  const response = await api.get(`/ai/analysis/${analysisId}`);
  return response.data;
}
