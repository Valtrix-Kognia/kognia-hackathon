import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { ChartBar, CircleAlert, Database, History, LucideAngularModule, Map as MapIcon, Sparkles } from 'lucide-angular';
import {
  CategoryChartSpec,
  ColombiaMapSpec,
  MetricSpec,
  TableSpec,
  VisualizationSpec,
} from '../../core/models/visualization.model';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { DashboardStateService } from '../../core/services/dashboard-state.service';
import { TOOL_LABELS, FILTER_LABELS } from '../../shared/utils/labels';
import { BarChartComponent } from './bar-chart.component';
import { DataTableComponent } from './data-table.component';
import { DonutChartComponent } from './donut-chart.component';
import { MetricTilesComponent } from './metric-tiles.component';

const SUGGESTIONS = [
  'Kognia, ¿cuántas IPS hay en el Quindío?',
  'Kognia, ¿qué departamentos tienen más sedes?',
  'Kognia, compara públicas y privadas en Antioquia.',
];

@Component({
  selector: 'app-visualization-panel',
  imports: [LucideAngularModule, DatePipe, MetricTilesComponent, BarChartComponent, DonutChartComponent, DataTableComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (dashboard.selectedQuery(); as q) {
      <div class="space-y-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            @if (q.question) {
              <p class="text-sm text-kv-muted">Pregunta</p>
              <p class="text-base font-medium text-kv-ink">“{{ q.question }}”</p>
            }
            <div class="mt-2 flex flex-wrap gap-1.5">
              <span class="chip bg-kv-primary/15 text-blue-200 ring-1 ring-kv-primary/30">{{ toolLabels[q.tool] }}</span>
              @for (f of filters(q); track f.key) {
                <span class="chip chip-neutral">{{ f.key }}: {{ f.value }}</span>
              }
            </div>
          </div>
          @if (store.queries().length > 1) {
            <label class="flex items-center gap-1.5 text-xs text-kv-muted">
              <lucide-icon [img]="historyIcon" [size]="14" />
              <span class="sr-only">Consultas anteriores</span>
              <select
                class="max-w-48 rounded-lg border border-kv-border bg-kv-elevated px-2 py-1.5 text-xs text-kv-ink"
                [value]="q.queryId"
                (change)="dashboard.selectedQueryId.set($any($event.target).value)"
              >
                @for (item of store.queries(); track item.queryId) {
                  <option [value]="item.queryId">{{ item.startedAt | date: 'HH:mm:ss' }} · {{ toolLabels[item.tool] }}</option>
                }
              </select>
            </label>
          }
        </div>

        @switch (q.status) {
          @case ('running') {
            <div class="space-y-3" aria-busy="true">
              <p class="flex items-center gap-2 text-sm text-violet-200"><lucide-icon [img]="dbIcon" [size]="16" class="animate-pulse" /> Consultando la API oficial…</p>
              <div class="grid grid-cols-3 gap-3"><div class="skeleton h-24"></div><div class="skeleton h-24"></div><div class="skeleton h-24"></div></div>
              <div class="skeleton h-40"></div>
            </div>
          }
          @case ('failed') {
            <div class="flex gap-3 rounded-xl border border-kv-danger/40 bg-kv-danger/10 p-4 text-sm text-red-100" role="alert">
              <lucide-icon [img]="alertIcon" [size]="18" class="shrink-0" />
              <p>{{ q.message || 'La consulta no pudo completarse.' }} No se muestra ninguna cifra para evitar información incorrecta.</p>
            </div>
          }
          @default {
            @for (spec of dashboard.specs(); track spec.id) {
              <section class="fade-in rounded-xl border border-kv-border bg-kv-bg/40 p-4" [attr.aria-label]="spec.title">
                <header class="mb-3">
                  <h3 class="text-sm font-semibold text-kv-ink">{{ spec.title }}</h3>
                  <p class="text-xs text-kv-muted">{{ spec.description }}</p>
                </header>
                @switch (spec.kind) {
                  @case ('metric') { <app-metric-tiles [spec]="asMetric(spec)" /> }
                  @case ('horizontal_bar') { <app-bar-chart [spec]="asCategory(spec)" /> }
                  @case ('bar_chart') { <app-bar-chart [spec]="asCategory(spec)" /> }
                  @case ('donut_chart') { <app-donut-chart [spec]="asCategory(spec)" /> }
                  @case ('table') { <app-data-table [spec]="asTable(spec)" /> }
                  @case ('colombia_map') {
                    <button type="button" class="btn-ghost w-full" (click)="dashboard.activeTab.set('mapa')">
                      <lucide-icon [img]="mapIcon" [size]="16" />
                      Ver {{ asMap(spec).data.length }} departamentos en el mapa de Colombia
                    </button>
                  }
                }
                <footer class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-kv-subtle">
                  <span>Unidad: {{ spec.unit }}</span>
                  <span>Fuente: datos.gov.co · {{ spec.provenance.metadata.dataset_id }}</span>
                  <span>Consultado {{ spec.provenance.metadata.queried_at | date: 'HH:mm:ss' }}</span>
                </footer>
              </section>
            } @empty {
              <p class="rounded-xl border border-dashed border-kv-border p-6 text-center text-sm text-kv-muted">
                Esta consulta no tiene una visualización asociada.
              </p>
            }
          }
        }
      </div>
    } @else {
      <div class="flex flex-col items-center gap-3 py-10 text-center">
        <span class="grid h-12 w-12 place-items-center rounded-2xl bg-kv-primary/10 text-kv-accent ring-1 ring-kv-primary/30">
          <lucide-icon [img]="chartIcon" [size]="22" />
        </span>
        <p class="text-sm font-medium text-kv-ink">Las respuestas de Kognia aparecerán aquí como gráficos</p>
        <p class="max-w-sm text-xs text-kv-muted">Todas las cifras vienen de consultas en vivo a la API oficial. Prueba con:</p>
        <ul class="space-y-1.5">
          @for (s of suggestions; track s) {
            <li class="flex items-center gap-2 text-sm text-kv-ink"><lucide-icon [img]="sparkIcon" [size]="14" class="text-kv-accent" /> {{ s }}</li>
          }
        </ul>
      </div>
    }
  `,
})
export class VisualizationPanelComponent {
  protected readonly store = inject(ConversationStore);
  protected readonly dashboard = inject(DashboardStateService);
  protected readonly toolLabels = TOOL_LABELS;
  protected readonly suggestions = SUGGESTIONS;
  protected readonly historyIcon = History;
  protected readonly alertIcon = CircleAlert;
  protected readonly dbIcon = Database;
  protected readonly mapIcon = MapIcon;
  protected readonly chartIcon = ChartBar;
  protected readonly sparkIcon = Sparkles;

  protected filters(q: { arguments: Record<string, unknown>; result: unknown }): { key: string; value: string }[] {
    const meta = (q.result as { metadata?: { filters: Record<string, string> } } | null)?.metadata;
    const source = meta?.filters ?? (q.arguments as Record<string, string>);
    return Object.entries(source)
      .filter(([, v]) => v !== null && v !== '' && typeof v !== 'object')
      .map(([k, v]) => ({ key: FILTER_LABELS[k] ?? k, value: String(v) }));
  }

  protected asMetric(spec: VisualizationSpec): MetricSpec {
    return spec as MetricSpec;
  }
  protected asCategory(spec: VisualizationSpec): CategoryChartSpec {
    return spec as CategoryChartSpec;
  }
  protected asTable(spec: VisualizationSpec): TableSpec {
    return spec as TableSpec;
  }
  protected asMap(spec: VisualizationSpec): ColombiaMapSpec {
    return spec as ColombiaMapSpec;
  }
}
