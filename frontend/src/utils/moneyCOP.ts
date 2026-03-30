const COP_INTEGER_REGEX = /[^\d-]/g;

const copNumberFormatter = new Intl.NumberFormat('es-CO', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const copCurrencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const normalizeInteger = (value: unknown): number => {
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return 0;
    return Math.trunc(value);
  }
  if (typeof value !== 'string') return 0;
  const cleaned = value.replace(COP_INTEGER_REGEX, '');
  if (!cleaned || cleaned === '-') return 0;
  const parsed = Number.parseInt(cleaned, 10);
  return Number.isNaN(parsed) ? 0 : parsed;
};

export const parseMoneyCOP = (input: unknown): number => {
  const value = normalizeInteger(input);
  return value < 0 ? 0 : value;
};

export const formatMoneyCOP = (value: unknown): string =>
  copNumberFormatter.format(parseMoneyCOP(value));

export const formatCurrencyCOP = (value: unknown): string =>
  copCurrencyFormatter.format(parseMoneyCOP(value));

export const roundCashCOP = (value: unknown, increment = 1): number => {
  const amount = parseMoneyCOP(value);
  const safeIncrement = Math.max(1, parseMoneyCOP(increment));
  return Math.round(amount / safeIncrement) * safeIncrement;
};

