import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, linkedSignal } from '@angular/core';
import { CircleAlert, History, LucideAngularModule, Search, TableProperties } from 'lucide-angular';
import { CountResult, DatasetOverview, GroupResult, IpsDetail, SearchResult } from '../../core/models/ips.model';
import { ConversationStore, TrackedQuery } from '../../core/services/conversation-store.service';
import { DIMENSION_LABELS, FILTER_LABELS, TOOL_LABELS, formatNumber } from '../../shared/utils/labels';
import { DataSourceBadgeComponent } from './data-source-badge.component';

@Component({
  selector: 'app-ips-results',
  imports: [LucideAngularModule, DataSourceBadgeComponent, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card" aria-labelledby="results-title">
      <header class="card-header">
        <h2 id="results-title" class="card-title">
          <lucide-icon [img]="tableIcon" [size]="16" class="text-brand-600" /> Resultados de la consulta
        </h2>
        @if (store.queries().length > 1) {
          <label class="flex items-center gap-1.5 text-xs text-slate-500">
            <lucide-icon [img]="historyIcon" [size]="14" />
            <span class="sr-only">Historial de consultas</span>
            <select
              class="max-w-44 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs"
              [value]="selectedId() ?? store.latestQuery()?.queryId ?? ''"
              (change)="selectedId.set($any($event.target).value)"
            >
              @for (q of store.queries(); track q.queryId) {
                <option [value]="q.queryId">{{ q.startedAt | date: 'HH:mm:ss' }} · {{ toolLabels[q.tool] }}</option>
              }
            </select>
          </label>
        }
      </header>

      <div class="p-5">
        @if (selected(); as q) {
          <div class="mb-4 space-y-2">
            @if (q.question) {
              <p class="text-sm text-slate-500">
                Pregunta: <span class="font-medium text-slate-800">“{{ q.question }}”</span>
              </p>
            }
            <div class="flex flex-wrap items-center gap-2">
              <span class="chip bg-brand-50 text-brand-700">{{ toolLabels[q.tool] }}</span>
              @for (f of filtersOf(q); track f.key) {
                <span class="chip bg-slate-100 text-slate-700">{{ f.key }}: {{ f.value }}</span>
              }
            </div>
          </div>

          @switch (q.status) {
            @case ('running') {
              <div class="space-y-3" aria-busy="true">
                <p class="text-sm text-violet-700">Consultando la API oficial…</p>
                <div class="skeleton h-16 w-full"></div>
                <div class="skeleton h-4 w-2/3"></div>
                <div class="skeleton h-4 w-1/2"></div>
              </div>
            }
            @case ('failed') {
              <div class="flex gap-3 rounded-xl border border-rose-100 bg-rose-50 p-4 text-sm text-rose-800" role="alert">
                <lucide-icon [img]="alertIcon" [size]="18" class="shrink-0" />
                <p>{{ q.message || 'La consulta no pudo completarse.' }} No se muestran datos para evitar información incorrecta.</p>
              </div>
            }
            @case ('completed') {
              @switch (q.tool) {
                @case ('count_ips') {
                  @if (asCount(q); as r) {
                    <div class="grid grid-cols-3 gap-3">
                      @for (stat of countStats(r); track stat.label) {
                        <div class="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-100">
                          <p class="text-2xl font-semibold tabular-nums text-slate-900">{{ stat.value }}</p>
                          <p class="mt-0.5 text-xs text-slate-500">{{ stat.label }}</p>
                        </div>
                      }
                    </div>
                  }
                }
                @case ('group_ips') {
                  @if (asGroup(q); as r) {
                    <p class="mb-3 text-xs text-slate-500">
                      {{ dimensionLabel(r.dimension) }} · métrica: {{ r.metric_description }}
                    </p>
                    <ol class="space-y-2">
                      @for (b of r.buckets; track b.label) {
                        <li class="grid grid-cols-[minmax(6rem,10rem)_1fr_auto] items-center gap-3 text-sm">
                          <span class="truncate text-slate-700" [title]="b.label">{{ b.label }}</span>
                          <span class="h-2 rounded-full bg-slate-100">
                            <span class="block h-2 rounded-full bg-brand-500" [style.width.%]="(b.value / maxBucket(r)) * 100"></span>
                          </span>
                          <span class="tabular-nums font-medium text-slate-900">{{ fmt(b.value) }}</span>
                        </li>
                      } @empty {
                        <li class="text-sm text-slate-500">La consulta no devolvió grupos.</li>
                      }
                    </ol>
                  }
                }
                @case ('search_ips') {
                  @if (asSearch(q); as r) {
                    <p class="mb-3 text-xs text-slate-500">{{ fmt(r.total_sedes) }} sede(s) encontradas · página {{ r.page }}</p>
                    <div class="-mx-5 overflow-x-auto">
                      <table class="min-w-full text-left text-sm">
                        <thead class="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                          <tr>
                            <th class="px-5 py-2 font-medium">Sede / prestador</th>
                            <th class="px-3 py-2 font-medium">Ubicación</th>
                            <th class="px-3 py-2 font-medium">Naturaleza</th>
                            <th class="px-5 py-2 font-medium">Nivel</th>
                          </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                          @for (s of r.items; track s.codigo_sede) {
                            <tr>
                              <td class="px-5 py-2">
                                <p class="font-medium text-slate-800">{{ s.nombre_sede }}</p>
                                <p class="text-xs text-slate-500">{{ s.nombre_prestador }} · sede {{ s.codigo_sede }}</p>
                              </td>
                              <td class="px-3 py-2 text-slate-600">{{ s.municipio }}, {{ s.departamento }}</td>
                              <td class="px-3 py-2 text-slate-600">{{ s.naturaleza ?? 'Sin dato' }}</td>
                              <td class="px-5 py-2 text-slate-600">{{ s.nivel_atencion ?? 'Sin dato' }}</td>
                            </tr>
                          } @empty {
                            <tr><td colspan="4" class="px-5 py-4 text-slate-500">No se encontraron sedes con esos criterios.</td></tr>
                          }
                        </tbody>
                      </table>
                    </div>
                  }
                }
                @case ('get_ips_details') {
                  @if (asDetail(q); as r) {
                    <div class="space-y-3">
                      <div>
                        <p class="font-semibold text-slate-900">{{ r.site.nombre_sede }}</p>
                        <p class="text-sm text-slate-500">{{ r.site.nombre_prestador }}</p>
                      </div>
                      <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
                        <div><dt class="text-xs text-slate-500">Ubicación</dt><dd>{{ r.site.municipio }}, {{ r.site.departamento }}</dd></div>
                        <div><dt class="text-xs text-slate-500">Naturaleza</dt><dd>{{ r.site.naturaleza ?? 'Sin dato' }}</dd></div>
                        <div><dt class="text-xs text-slate-500">Nivel</dt><dd>{{ r.site.nivel_atencion ?? 'Sin dato' }}</dd></div>
                        <div class="col-span-2"><dt class="text-xs text-slate-500">Dirección</dt><dd>{{ r.site.direccion ?? 'Sin dato' }}</dd></div>
                        <div><dt class="text-xs text-slate-500">Teléfono</dt><dd>{{ r.site.telefono ?? 'Sin dato' }}</dd></div>
                      </dl>
                      <ul class="divide-y divide-slate-100 rounded-xl ring-1 ring-slate-100">
                        @for (c of r.capacidades; track $index) {
                          <li class="flex justify-between px-3 py-1.5 text-sm">
                            <span class="text-slate-600">{{ c.grupo }} · {{ c.descripcion }}</span>
                            <span class="tabular-nums font-medium">{{ fmt(c.cantidad) }}</span>
                          </li>
                        }
                      </ul>
                    </div>
                  }
                }
                @case ('get_dataset_overview') {
                  @if (asOverview(q); as r) {
                    <div class="space-y-3 text-sm">
                      <p class="font-semibold text-slate-900">{{ r.name }}</p>
                      <p class="text-slate-600">{{ r.attribution }} · actualizado {{ r.rows_updated_at | date: 'longDate' }}</p>
                      <div class="grid grid-cols-3 gap-3">
                        @for (stat of countStats(r.totals); track stat.label) {
                          <div class="rounded-xl bg-slate-50 p-3 ring-1 ring-slate-100">
                            <p class="text-xl font-semibold tabular-nums">{{ stat.value }}</p>
                            <p class="text-xs text-slate-500">{{ stat.label }}</p>
                          </div>
                        }
                      </div>
                    </div>
                  }
                }
              }

              @if (limitations(q).length) {
                <ul class="mt-4 space-y-1 rounded-xl bg-amber-50/70 px-4 py-3 text-xs text-amber-900">
                  @for (note of limitations(q); track note) {
                    <li>• {{ note }}</li>
                  }
                </ul>
              }
              @if (metadataOf(q); as meta) {
                <div class="mt-4"><app-data-source-badge [metadata]="meta" /></div>
              }
            }
          }
        } @else {
          <div class="flex flex-col items-center gap-2 py-10 text-center text-sm text-slate-400">
            <lucide-icon [img]="searchIcon" [size]="28" />
            <p>Pregunta, por ejemplo:</p>
            <p class="text-slate-500">“¿Cuántas IPS hay en el Quindío?” · “¿Qué departamentos tienen más prestadores?”</p>
          </div>
        }
      </div>
    </section>
  `,
})
export class IpsResultsComponent {
  protected readonly store = inject(ConversationStore);
  protected readonly toolLabels = TOOL_LABELS;
  protected readonly tableIcon = TableProperties;
  protected readonly historyIcon = History;
  protected readonly alertIcon = CircleAlert;
  protected readonly searchIcon = Search;
  protected readonly fmt = formatNumber;

  /** Resets to the newest query whenever a new one arrives; the dropdown can pin an older one. */
  protected readonly selectedId = linkedSignal<string | undefined, string | null>({
    source: () => this.store.latestQuery()?.queryId,
    computation: () => null,
  });
  protected readonly selected = computed(() => {
    const queries = this.store.queries();
    const id = this.selectedId();
    return (id && queries.find((q) => q.queryId === id)) || queries[0] || null;
  });

  protected filtersOf(q: TrackedQuery): { key: string; value: string }[] {
    const meta = this.metadataOf(q);
    const source = meta?.filters ?? (q.arguments as Record<string, string>);
    return Object.entries(source)
      .filter(([, v]) => v !== null && v !== '' && typeof v !== 'object')
      .map(([k, v]) => ({ key: FILTER_LABELS[k] ?? k, value: String(v) }));
  }

  protected asCount(q: TrackedQuery): CountResult | null {
    return q.tool === 'count_ips' ? (q.result as CountResult) : null;
  }
  protected asGroup(q: TrackedQuery): GroupResult | null {
    return q.tool === 'group_ips' ? (q.result as GroupResult) : null;
  }
  protected asSearch(q: TrackedQuery): SearchResult | null {
    return q.tool === 'search_ips' ? (q.result as SearchResult) : null;
  }
  protected asDetail(q: TrackedQuery): IpsDetail | null {
    return q.tool === 'get_ips_details' ? (q.result as IpsDetail) : null;
  }
  protected asOverview(q: TrackedQuery): DatasetOverview | null {
    return q.tool === 'get_dataset_overview' ? (q.result as DatasetOverview) : null;
  }

  protected countStats(r: CountResult) {
    return [
      { label: 'Prestadores únicos', value: formatNumber(r.prestadores) },
      { label: 'Sedes únicas', value: formatNumber(r.sedes) },
      { label: 'Registros (líneas de capacidad)', value: formatNumber(r.registros) },
    ];
  }

  protected maxBucket(r: GroupResult): number {
    return Math.max(1, ...r.buckets.map((b) => b.value));
  }

  protected dimensionLabel(dimension: string): string {
    return DIMENSION_LABELS[dimension] ?? dimension;
  }

  protected metadataOf(q: TrackedQuery) {
    const result = q.result as { metadata?: CountResult['metadata']; totals?: CountResult } | null;
    return result?.metadata ?? result?.totals?.metadata ?? null;
  }

  protected limitations(q: TrackedQuery): string[] {
    const result = q.result as { limitations?: string[] } | null;
    return result?.limitations ?? this.metadataOf(q)?.limitations ?? [];
  }
}
