import { useHealth } from '../../hooks/useHealth';

function StatusCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'green' | 'blue' | 'purple';
}) {
  const tones = {
    green: 'bg-green-50 border-green-200 text-green-800',
    blue: 'bg-blue-50 border-blue-200 text-blue-800',
    purple: 'bg-purple-50 border-purple-200 text-purple-800',
  } as const;

  return (
    <div className={`rounded-md border p-4 ${tones[tone]}`}>
      <p className="text-sm font-medium opacity-70">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}

function HomePage() {
  const { health, error, loading } = useHealth();

  return (
    <section className="overflow-hidden rounded-lg bg-white shadow">
      <div className="px-4 py-5 sm:p-6">
        <h2 className="mb-4 text-lg font-medium text-gray-900">
          Estado del Sistema
        </h2>
        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-4">
            <p className="text-red-800">{error}</p>
          </div>
        ) : loading ? (
          <div className="animate-pulse">
            <div className="mb-4 h-4 w-1/4 rounded bg-gray-200" />
            <div className="h-4 w-1/2 rounded bg-gray-200" />
          </div>
        ) : health ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatusCard
              label="Estado"
              value={health.status === 'healthy' ? 'Saludable' : 'Degradado'}
              tone="green"
            />
            <StatusCard
              label="Base de Datos"
              value={health.database === 'ok' ? 'Conectada' : 'Error'}
              tone="blue"
            />
            <StatusCard label="Entorno" value={health.environment} tone="purple" />
          </div>
        ) : null}
      </div>
    </section>
  );
}

export default HomePage;
