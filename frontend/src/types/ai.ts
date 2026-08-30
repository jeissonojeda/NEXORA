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
