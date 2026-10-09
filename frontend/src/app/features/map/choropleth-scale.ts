export const SEQUENTIAL_RAMP = [
  'var(--kv-seq-1)',
  'var(--kv-seq-2)',
  'var(--kv-seq-3)',
  'var(--kv-seq-4)',
  'var(--kv-seq-5)',
  'var(--kv-seq-6)',
];

export interface ChoroplethClass {
  min: number;
  max: number;
  color: string;
}

/** Quantile classes over the observed values (the distribution is heavily skewed). */
export function quantileClasses(values: number[], classes = SEQUENTIAL_RAMP.length): ChoroplethClass[] {
  const sorted = [...values].filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (!sorted.length) return [];
  const result: ChoroplethClass[] = [];
  let previousMax = Number.NEGATIVE_INFINITY;
  for (let i = 0; i < classes; i++) {
    const hi = sorted[Math.min(sorted.length - 1, Math.ceil(((i + 1) * sorted.length) / classes) - 1)];
    const lo = sorted.find((v) => v > previousMax);
    if (lo === undefined || hi < lo) continue;
    result.push({ min: lo, max: hi, color: SEQUENTIAL_RAMP[Math.round((i * (SEQUENTIAL_RAMP.length - 1)) / Math.max(1, classes - 1))] });
    previousMax = hi;
  }
  return result;
}

export function colorFor(value: number | undefined, classes: ChoroplethClass[]): string | null {
  if (value === undefined) return null;
  const match = classes.find((c) => value >= c.min && value <= c.max);
  return match?.color ?? classes.at(-1)?.color ?? null;
}
