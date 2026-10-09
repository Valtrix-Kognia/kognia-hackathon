import { Injectable, computed, effect, inject, linkedSignal, untracked } from '@angular/core';
import { GroupResult } from '../models/ips.model';
import { VisualizationSpec } from '../models/visualization.model';
import { MapStateService } from '../../features/map/map-state.service';
import { ConversationStore, TrackedQuery } from './conversation-store.service';
import { buildVisualizations } from './visualization-builder';

export type AnalysisTab = 'visualizacion' | 'mapa' | 'evidencia' | 'analisis';

/** Connects completed tool results with the generative dashboard and the map. */
@Injectable({ providedIn: 'root' })
export class DashboardStateService {
  private readonly store = inject(ConversationStore);
  private readonly map = inject(MapStateService);
  private lastMappedQuery: string | null = null;

  /** The query shown in the dashboard: the newest one unless the user pins another. */
  readonly selectedQueryId = linkedSignal<string | undefined, string | null>({
    source: () => this.store.latestQuery()?.queryId,
    computation: () => null,
  });

  readonly activeTab = linkedSignal<string | undefined, AnalysisTab>({
    source: () => this.store.latestQuery()?.queryId,
    computation: (_source, previous) => previous?.value ?? 'visualizacion',
  });

  readonly selectedQuery = computed<TrackedQuery | null>(() => {
    const id = this.selectedQueryId();
    const queries = this.store.queries();
    return (id && queries.find((q) => q.queryId === id)) || queries[0] || null;
  });

  readonly specs = computed<VisualizationSpec[]>(() => {
    const query = this.selectedQuery();
    return query ? buildVisualizations(query) : [];
  });

  constructor() {
    effect(() => {
      const query = this.store.latestQuery();
      if (!query || query.status !== 'completed' || query.tool !== 'group_ips') return;
      const result = query.result as GroupResult | null;
      if (!result || result.dimension !== 'departamento' || this.lastMappedQuery === query.queryId) return;
      this.lastMappedQuery = query.queryId;
      untracked(() => this.map.applyAgentRanking(result));
    });
  }
}
