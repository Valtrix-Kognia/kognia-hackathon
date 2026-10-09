import { GroupResult, QueryMetadata } from '../models/ips.model';
import { TrackedQuery } from './conversation-store.service';
import { buildVisualizations } from './visualization-builder';

const META: QueryMetadata = {
  dataset_id: 's2ru-bqt6',
  source: 'https://www.datos.gov.co/api/v3/views/s2ru-bqt6/query.json',
  queried_at: '2026-10-09T15:00:00Z',
  filters: {},
  limitations: [],
};

function query(tool: TrackedQuery['tool'], result: unknown, status: TrackedQuery['status'] = 'completed'): TrackedQuery {
  return { queryId: 'q1', tool, arguments: {}, status, result: result as TrackedQuery['result'], startedAt: '2026-10-09T15:00:00Z' };
}

function group(dimension: string, metric: GroupResult['metric'], labels: string[]): GroupResult {
  return {
    dimension,
    metric,
    metric_description: 'desc',
    buckets: labels.map((label, i) => ({ label, value: 100 - i })),
    metadata: META,
  };
}

describe('buildVisualizations', () => {
  it('produces nothing for running or failed queries', () => {
    expect(buildVisualizations(query('count_ips', null, 'running'))).toEqual([]);
    expect(buildVisualizations(query('count_ips', null, 'failed'))).toEqual([]);
  });

  it('turns a count into metric tiles with explicit units, copying API values', () => {
    const [spec] = buildVisualizations(
      query('count_ips', { registros: 469, prestadores: 139, sedes: 148, metadata: { ...META, filters: { departamento: 'Quindío' } } }),
    );
    expect(spec.kind).toBe('metric');
    expect(spec.title).toContain('Quindío');
    expect(spec.kind === 'metric' && spec.items.map((i) => i.value)).toEqual([139, 148, 469]);
    expect(spec.provenance.metadata.dataset_id).toBe('s2ru-bqt6');
  });

  it('maps department rankings of sedes to map + bars + table', () => {
    const kinds = buildVisualizations(query('group_ips', group('departamento', 'sedes', ['Bogotá D.C', 'Antioquia']))).map((s) => s.kind);
    expect(kinds).toEqual(['colombia_map', 'horizontal_bar', 'table']);
  });

  it('never maps unique providers (not additive across territories)', () => {
    const kinds = buildVisualizations(query('group_ips', group('departamento', 'prestadores', ['Bogotá D.C']))).map((s) => s.kind);
    expect(kinds).not.toContain('colombia_map');
  });

  it('uses a donut for few categories and never a line chart', () => {
    const specs = buildVisualizations(query('group_ips', group('naturaleza', 'sedes', ['Privada', 'Pública', 'Mixta'])));
    expect(specs.map((s) => s.kind)).toEqual(['donut_chart', 'table']);
    expect(specs.some((s) => s.kind === 'line_chart')).toBe(false);
  });
});
