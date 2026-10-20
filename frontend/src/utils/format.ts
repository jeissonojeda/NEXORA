export interface CurrencyConfig {
  code: string;
  symbol: string;
  locale: string;
  decimals: number;
}

const DEFAULT_CURRENCY: CurrencyConfig = {
  code: 'COP',
  symbol: '$',
  locale: 'es-CO',
  decimals: 2,
};

let currencyConfig: CurrencyConfig = DEFAULT_CURRENCY;

export function configureCurrency(config: Partial<CurrencyConfig> | null | undefined) {
  currencyConfig = {
    ...DEFAULT_CURRENCY,
    ...(config ?? {}),
  };
}

export function getCurrencyConfig(): CurrencyConfig {
  return currencyConfig;
}

export function formatCurrency(value: string | number): string {
  const amount = typeof value === 'string' ? parseFloat(value) : value;
  if (Number.isNaN(amount)) return '—';
  try {
    return amount.toLocaleString(currencyConfig.locale, {
      style: 'currency',
      currency: currencyConfig.code,
      minimumFractionDigits: currencyConfig.decimals,
      maximumFractionDigits: currencyConfig.decimals,
    });
  } catch {
    return `${currencyConfig.symbol}${amount.toFixed(currencyConfig.decimals)}`;
  }
}

export function formatDateTime(value: string): string {
  if (!value) return '—';
  return new Date(value).toLocaleString('es-CO', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
}
