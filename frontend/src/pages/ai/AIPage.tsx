import { useState } from 'react';
import { useAsync, extractErrorMessage } from '../../hooks/useAsync';
import api from '../../services/api';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import Icon from '../../components/ui/Icon';
import LoadingState from '../../components/ui/LoadingState';
import PageHeader from '../../components/ui/PageHeader';

interface AIAnalysis {
  id: string;
  analysis_type: string;
  product_id?: string;
  category_id?: string;
  query: string;
  response: string;
  confidence_score: number;
  recommendations?: string[];
  created_at: string;
}

interface AITrend {
  product_id?: string;
  category_id?: string;
  trend_direction: string;
  trend_strength: number;
  forecast?: Array<{ date: string; predicted_quantity: number }>;
  insights: string[];
  recommendations: string[];
  confidence_score: number;
}

function ConfidenceBadge({ score }: { score: number }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        score >= 80
          ? 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300'
          : score >= 60
            ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
            : 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300'
      }`}
    >
      {score}% confianza
    </span>
  );
}

function TrendDirection({ direction }: { direction: string }) {
  if (direction === 'up')
    return <Icon name="trending-up" className="text-green-500" />;
  if (direction === 'down')
    return <Icon name="trending-down" className="text-red-500" />;
  return <Icon name="trending-up" className="text-muted" />;
}

export default function AIPage() {
  const [activeTab, setActiveTab] = useState<'analyze' | 'trends' | 'history'>('analyze');
  const [query, setQuery] = useState('');
  const [analysisType, setAnalysisType] = useState('reorder');
  const [selectedProduct, setSelectedProduct] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [timeRange, setTimeRange] = useState(30);
  const [includeRecommendations, setIncludeRecommendations] = useState(true);
  const [currentAnalysis, setCurrentAnalysis] = useState<AIAnalysis | null>(null);
  const [currentTrend, setCurrentTrend] = useState<AITrend | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch analysis history
  const { data: analyses, loading: historyLoading, reload: reloadHistory } = useAsync<AIAnalysis[]>(async () => {
    const response = await api.get('/ai/analysis?limit=50');
    return response.data;
  }, []);

  // Fetch products and categories for selection
  const { data: products } = useAsync(async () => {
    const response = await api.get('/products?limit=100');
    return response.data.items || [];
  }, []);

  const { data: categories } = useAsync(async () => {
    const response = await api.get('/categories');
    return response.data;
  }, []);

  const performAnalysis = async () => {
    if (!query.trim()) {
      setError('Por favor ingrese una consulta para analizar');
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    try {
      const response = await api.post('/ai/analyze', {
        analysis_type: analysisType,
        query: query,
        product_id: selectedProduct || null,
        category_id: selectedCategory || null,
        time_range_days: timeRange,
        include_recommendations: includeRecommendations
      });

      setCurrentAnalysis(response.data);
      reloadHistory();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const analyzeTrends = async () => {
    setIsAnalyzing(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (selectedProduct) params.append('product_id', selectedProduct);
      if (selectedCategory) params.append('category_id', selectedCategory);
      params.append('period_days', timeRange.toString());
      params.append('include_forecast', 'true');

      const response = await api.get(`/ai/trends?${params.toString()}`);
      setCurrentTrend(response.data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const tabs: { key: 'analyze' | 'trends' | 'history'; label: string }[] = [
    { key: 'analyze', label: 'Análisis' },
    { key: 'trends', label: 'Tendencias' },
    { key: 'history', label: 'Historial' },
  ];

  return (
    <div className="animate-fade-in space-y-6">
      <PageHeader
        title="NEXORA AI"
        subtitle="Análisis inteligente y recomendaciones para tu negocio."
      />

      {error && <ErrorAlert message={error} />}

      {/* Tabs */}
      <div className="border-b border-line">
        <nav className="-mb-px flex space-x-6">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`border-b-2 px-1 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted hover:border-line-strong hover:text-foreground'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Analysis Tab */}
      {activeTab === 'analyze' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="nx-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">Configurar Análisis</h2>

            <div className="space-y-4">
              <div>
                <label className="nx-label">Tipo de Análisis</label>
                <select
                  value={analysisType}
                  onChange={(e) => setAnalysisType(e.target.value)}
                  className="nx-select"
                >
                  <option value="reorder">Reorden de Productos</option>
                  <option value="trend">Análisis de Tendencias</option>
                  <option value="anomaly">Detección de Anomalías</option>
                  <option value="recommendation">Recomendaciones</option>
                </select>
              </div>

              <div>
                <label className="nx-label">Consulta en Lenguaje Natural</label>
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  rows={4}
                  placeholder="Ejemplo: ¿Qué productos necesitan reabastecimiento urgente? ¿Cuáles son los productos más vendidos este mes?"
                  className="nx-textarea"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="nx-label">Producto Específico (opcional)</label>
                  <select
                    value={selectedProduct}
                    onChange={(e) => setSelectedProduct(e.target.value)}
                    className="nx-select"
                  >
                    <option value="">Todos los productos</option>
                    {products?.map((product: any) => (
                      <option key={product.id} value={product.id}>
                        {product.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="nx-label">Categoría (opcional)</label>
                  <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="nx-select"
                  >
                    <option value="">Todas las categorías</option>
                    {categories?.map((category: any) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="nx-label">Período (días)</label>
                  <input
                    type="number"
                    value={timeRange}
                    onChange={(e) => setTimeRange(parseInt(e.target.value) || 30)}
                    min={7}
                    max={365}
                    className="nx-input"
                  />
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="includeRecommendations"
                    checked={includeRecommendations}
                    onChange={(e) => setIncludeRecommendations(e.target.checked)}
                    className="h-4 w-4 rounded border-line-strong accent-[var(--nx-primary)]"
                  />
                  <label htmlFor="includeRecommendations" className="ml-2 text-sm text-foreground">
                    Incluir recomendaciones
                  </label>
                </div>
              </div>

              <button
                onClick={performAnalysis}
                disabled={isAnalyzing || !query.trim()}
                className="nx-btn nx-btn-primary w-full"
              >
                {isAnalyzing ? 'Analizando…' : 'Ejecutar Análisis'}
              </button>
            </div>
          </div>

          <div className="nx-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">Resultado del Análisis</h2>

            {currentAnalysis ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-muted">Confianza:</span>
                  <ConfidenceBadge score={currentAnalysis.confidence_score} />
                </div>

                <div className="rounded-xl bg-surface p-4">
                  <h3 className="mb-2 font-medium text-foreground">Respuesta:</h3>
                  <p className="whitespace-pre-wrap text-muted">{currentAnalysis.response}</p>
                </div>

                {currentAnalysis.recommendations && currentAnalysis.recommendations.length > 0 && (
                  <div className="rounded-xl bg-primary-soft p-4">
                    <h3 className="mb-2 font-medium text-primary">Recomendaciones:</h3>
                    <ul className="space-y-2">
                      {currentAnalysis.recommendations.map((rec, index) => (
                        <li key={index} className="flex items-start text-primary">
                          <span className="mr-2">•</span>
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="text-xs text-faint">
                  Analizado: {new Date(currentAnalysis.created_at).toLocaleString()}
                </div>
              </div>
            ) : isAnalyzing ? (
              <div className="space-y-3" aria-label="Analizando">
                <LoadingState rows={3} />
                <p className="py-4 text-center text-sm text-muted">
                  Analizando… esto puede tardar unos segundos.
                </p>
              </div>
            ) : (
              <EmptyState
                title="Sin análisis"
                hint="Configure y ejecute un análisis para ver los resultados aquí"
                icon="sparkles"
              />
            )}
          </div>
        </div>
      )}

      {/* Trends Tab */}
      {activeTab === 'trends' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="nx-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">Configurar Análisis de Tendencias</h2>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="nx-label">Producto (opcional)</label>
                  <select
                    value={selectedProduct}
                    onChange={(e) => setSelectedProduct(e.target.value)}
                    className="nx-select"
                  >
                    <option value="">Todos los productos</option>
                    {products?.map((product: any) => (
                      <option key={product.id} value={product.id}>
                        {product.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="nx-label">Categoría (opcional)</label>
                  <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="nx-select"
                  >
                    <option value="">Todas las categorías</option>
                    {categories?.map((category: any) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="nx-label">Período de Análisis (días)</label>
                <select
                  value={timeRange}
                  onChange={(e) => setTimeRange(parseInt(e.target.value))}
                  className="nx-select"
                >
                  <option value={7}>Últimos 7 días</option>
                  <option value={30}>Últimos 30 días</option>
                  <option value={90}>Últimos 90 días</option>
                  <option value={180}>Últimos 6 meses</option>
                  <option value={365}>Último año</option>
                </select>
              </div>

              <button
                onClick={analyzeTrends}
                disabled={isAnalyzing}
                className="nx-btn nx-btn-success w-full"
              >
                {isAnalyzing ? 'Analizando…' : 'Analizar Tendencias'}
              </button>
            </div>
          </div>

          <div className="nx-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">Resultado de Tendencias</h2>

            {currentTrend ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-lg font-medium text-foreground">
                    <TrendDirection direction={currentTrend.trend_direction} />
                    Tendencia: {currentTrend.trend_direction.toUpperCase()}
                  </span>
                  <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-medium bg-primary-soft text-primary">
                    {currentTrend.confidence_score}%
                  </span>
                </div>

                <div className="rounded-xl bg-surface p-4">
                  <h3 className="mb-2 font-medium text-foreground">Fuerza de la Tendencia:</h3>
                  <div className="h-2.5 w-full rounded-full bg-line-strong">
                    <div
                      className="h-2.5 rounded-full nx-brand-gradient"
                      style={{ width: `${currentTrend.trend_strength}%` }}
                    />
                  </div>
                  <p className="mt-1 text-sm text-muted">{currentTrend.trend_strength}%</p>
                </div>

                {currentTrend.insights.length > 0 && (
                  <div className="rounded-xl bg-amber-50 p-4 text-amber-800 dark:bg-amber-400/10 dark:text-amber-200">
                    <h3 className="mb-2 font-medium">Insights:</h3>
                    <ul className="space-y-2">
                      {currentTrend.insights.map((insight, index) => (
                        <li key={index} className="flex items-start">
                          <span className="mr-2">•</span>
                          {insight}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {currentTrend.recommendations.length > 0 && (
                  <div className="rounded-xl bg-green-50 p-4 text-green-800 dark:bg-green-500/10 dark:text-green-200">
                    <h3 className="mb-2 font-medium">Recomendaciones:</h3>
                    <ul className="space-y-2">
                      {currentTrend.recommendations.map((rec, index) => (
                        <li key={index} className="flex items-start">
                          <span className="mr-2">•</span>
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {currentTrend.forecast && currentTrend.forecast.length > 0 && (
                  <div className="rounded-xl bg-primary-soft p-4">
                    <h3 className="mb-2 font-medium text-primary">Pronóstico (próximos 7 días):</h3>
                    <div className="space-y-1">
                      {currentTrend.forecast.map((item, index) => (
                        <div key={index} className="flex justify-between text-sm text-primary">
                          <span>
                            {new Date(item.date).toLocaleDateString()}
                          </span>
                          <span className="font-medium">
                            {item.predicted_quantity} unidades
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : isAnalyzing ? (
              <div className="space-y-3" aria-label="Analizando">
                <LoadingState rows={3} />
                <p className="py-4 text-center text-sm text-muted">
                  Analizando tendencias…
                </p>
              </div>
            ) : (
              <EmptyState
                title="Sin tendencias"
                hint="Seleccione filtros y analice para ver las tendencias de inventario"
                icon="trending-up"
              />
            )}
          </div>
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="nx-card overflow-hidden">
          <div className="border-b border-line p-6">
            <h2 className="text-lg font-semibold text-foreground">Historial de Análisis</h2>
          </div>

          {historyLoading ? (
            <div className="p-6">
              <LoadingState rows={4} />
            </div>
          ) : analyses && analyses.length > 0 ? (
            <div className="divide-y divide-line">
              {analyses.map((analysis) => (
                <div key={analysis.id} className="p-4 hover:bg-surface-2">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3">
                        <span className="inline-flex items-center rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-medium text-primary">
                          {analysis.analysis_type}
                        </span>
                        <ConfidenceBadge score={analysis.confidence_score} />
                      </div>
                      <p className="mt-1 text-sm text-muted">{analysis.query}</p>
                      <p className="mt-1 text-xs text-faint">
                        {new Date(analysis.created_at).toLocaleString()}
                      </p>
                    </div>
                    <button
                      onClick={() => setCurrentAnalysis(analysis)}
                      className="ml-4 text-sm font-medium text-primary hover:underline"
                    >
                      Ver detalle
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6">
              <EmptyState
                title="Sin historial"
                hint="Realice su primer análisis para comenzar a acumular historial"
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}