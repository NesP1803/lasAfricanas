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

  const cleaned = value.trim().replace(/[^\d,.-]/g, '');
  if (!cleaned || cleaned === '-' || cleaned === ',' || cleaned === '.') return 0;

  let normalized = cleaned;
  const lastDot = normalized.lastIndexOf('.');
  const lastComma = normalized.lastIndexOf(',');
  const hasDot = lastDot !== -1;
  const hasComma = lastComma !== -1;

  if (hasDot && hasComma) {
    const decimalSeparator = lastDot > lastComma ? '.' : ',';
    const thousandsSeparator = decimalSeparator === '.' ? ',' : '.';
    normalized = normalized.split(thousandsSeparator).join('');
    normalized = normalized.replace(decimalSeparator, '.');
  } else if (hasComma) {
    const commaThousands = /^-?\d{1,3}(,\d{3})+$/.test(normalized);
    normalized = commaThousands
      ? normalized.replace(/,/g, '')
      : normalized.replace(',', '.');
  } else if (hasDot) {
    const dotThousands = /^-?\d{1,3}(\.\d{3})+$/.test(normalized);
    normalized = dotThousands ? normalized.replace(/\./g, '') : normalized;
  }

  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) return 0;
  return Math.trunc(parsed);
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
