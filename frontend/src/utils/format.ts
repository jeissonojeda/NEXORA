export function formatCurrency(value: string | number): string {
  const amount = typeof value === 'string' ? parseFloat(value) : value;
  if (Number.isNaN(amount)) return '—';
  return amount.toLocaleString('es-CR', {
    style: 'currency',
    currency: 'CRC',
    minimumFractionDigits: 2,
  });
}

export function formatDateTime(value: string): string {
  if (!value) return '—';
  return new Date(value).toLocaleString('es-CR', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
}
