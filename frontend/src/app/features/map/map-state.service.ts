import { Injectable, computed, inject, signal } from '@angular/core';
import { Subscription, forkJoin } from 'rxjs';
import { CountResult, GroupResult, QueryMetadata } from '../../core/models/ips.model';
import { MapMetric } from '../../core/models/visualization.model';
import { IpsApiService } from '../../core/services/ips-api.service';
import { AggregatedByDepartment, aggregateByDepartment, isoForDatasetValue } from './department-catalog';

export type LoadState = 'idle' | 'loading' | 'ready' | 'error';

export interface MapContext {
  metric: MapMetric;
  naturaleza: string | null;
  /** Departments named in Kognia's latest ranking (highlighted, never used as values). */
  highlighted: string[];
  origin: 'exploracion' | 'respuesta_kognia';
}

export interface DepartmentSourceStats {
  label: string;
  result: CountResult;
}

/** Shared state of the Colombia map: metric, filters, selection and official data. */
@Injectable({ providedIn: 'root' })
export class MapStateService {
  private readonly api = inject(IpsApiService);
  private dataSub?: Subscription;
  private statsSub?: Subscription;

  readonly context = signal<MapContext>({ metric: 'sedes', naturaleza: null, highlighted: [], origin: 'exploracion' });
  readonly dataState = signal<LoadState>('idle');
  readonly aggregated = signal<AggregatedByDepartment | null>(null);
  readonly metadata = signal<QueryMetadata | null>(null);
  readonly selectedIso = signal<string | null>(null);
  readonly statsState = signal<LoadState>('idle');
  readonly selectedStats = signal<DepartmentSourceStats[]>([]);
  readonly naturalezaBreakdown = signal<GroupResult | null>(null);

  readonly maxValue = computed(() => {
    const values = this.aggregated()?.values;
    return values ? Math.max(0, ...[...values.values()].map((v) => v.value)) : 0;
  });

  ensureLoaded(): void {
    if (this.dataState() === 'idle') this.load();
  }

  setMetric(metric: MapMetric): void {
    this.context.update((c) => ({ ...c, metric, origin: 'exploracion' }));
    this.load();
  }

  setNaturaleza(naturaleza: string | null): void {
    this.context.update((c) => ({ ...c, naturaleza, origin: 'exploracion' }));
    this.load();
    const iso = this.selectedIso();
    if (iso) this.loadStats(iso);
  }

  /** Called when Kognia answers with a ranking by department. */
  applyAgentRanking(result: GroupResult): void {
    const metric: MapMetric = result.metric === 'registros' ? 'registros' : 'sedes';
    const highlighted = result.buckets
      .map((b) => isoForDatasetValue(b.label)?.iso)
      .filter((iso): iso is string => !!iso);
    this.context.set({
      metric,
      naturaleza: result.metadata.filters['naturaleza'] ?? null,
      highlighted: [...new Set(highlighted)],
      origin: 'respuesta_kognia',
    });
    this.load();
  }

  select(iso: string | null, sources: string[] = []): void {
    this.selectedIso.set(iso);
    if (iso) this.loadStats(iso, sources);
    else {
      this.statsSub?.unsubscribe();
      this.selectedStats.set([]);
      this.naturalezaBreakdown.set(null);
      this.statsState.set('idle');
    }
  }

  private load(): void {
    const { metric, naturaleza } = this.context();
    this.dataSub?.unsubscribe();
    this.dataState.set('loading');
    this.dataSub = this.api.groupByDepartment(metric, { naturaleza }).subscribe({
      next: (result) => {
        this.aggregated.set(aggregateByDepartment(result.buckets.map((b) => ({ label: b.label, value: b.value }))));
        this.metadata.set(result.metadata);
        this.dataState.set('ready');
      },
      error: () => this.dataState.set('error'),
    });
  }

  private loadStats(iso: string, sources: string[] = []): void {
    const known = this.aggregated()?.values.get(iso)?.sources ?? [];
    const labels = sources.length ? sources : known;
    this.statsSub?.unsubscribe();
    if (!labels.length) {
      this.selectedStats.set([]);
      this.naturalezaBreakdown.set(null);
      this.statsState.set('ready');
      return;
    }
    const naturaleza = this.context().naturaleza;
    this.statsState.set('loading');
    this.statsSub = forkJoin({
      counts: forkJoin(labels.map((label) => this.api.count({ departamento: label, naturaleza }))),
      breakdown: this.api.groupBy('naturaleza', 'sedes', { departamento: labels[0] }),
    }).subscribe({
      next: ({ counts, breakdown }) => {
        this.selectedStats.set(counts.map((result, i) => ({ label: labels[i], result })));
        this.naturalezaBreakdown.set(breakdown);
        this.statsState.set('ready');
      },
      error: () => this.statsState.set('error'),
    });
  }
}
