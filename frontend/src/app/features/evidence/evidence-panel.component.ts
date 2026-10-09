import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { BadgeCheck, CircleAlert, Database, FileWarning, LucideAngularModule, MessageSquareQuote, Zap } from 'lucide-angular';
import { QueryMetadata } from '../../core/models/ips.model';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { DashboardStateService } from '../../core/services/dashboard-state.service';
import { FILTER_LABELS, TOOL_LABELS } from '../../shared/utils/labels';

const CACHE_MARKER = 'agregados descargados';

@Component({
  selector: 'app-evidence-panel',
  imports: [LucideAngularModule, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (evidence(); as e) {
      <div class="space-y-4">
        <section class="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4" aria-labelledby="ev-verified">
          <h3 id="ev-verified" class="flex items-center gap-2 text-sm font-semibold text-emerald-200">
            <lucide-icon [img]="verifiedIcon" [size]="16" /> Datos verificados en la fuente oficial
          </h3>
          <dl class="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            <div><dt class="eyebrow">Fuente</dt><dd>Ministerio de Salud · datos.gov.co</dd></div>
            <div><dt class="eyebrow">Dataset</dt><dd class="font-mono text-xs">{{ e.meta?.dataset_id ?? 's2ru-bqt6' }}</dd></div>
            <div><dt class="eyebrow">Herramienta</dt><dd>{{ e.tool }}</dd></div>
            <div>
              <dt class="eyebrow">Consultado</dt>
              <dd>
                {{ e.meta?.queried_at | date: 'dd/MM/yyyy HH:mm:ss' }}
                @if (e.cached) {
                  <span class="chip ml-1 bg-kv-accent/10 text-cyan-200 ring-1 ring-kv-accent/30"><lucide-icon [img]="zapIcon" [size]="11" /> caché de agregados</span>
                }
              </dd>
            </div>
            <div class="sm:col-span-2">
              <dt class="eyebrow">Filtros aplicados</dt>
              <dd class="mt-1 flex flex-wrap gap-1.5">
                @for (f of e.filters; track f.key) {
                  <span class="chip chip-neutral">{{ f.key }}: {{ f.value }}</span>
                } @empty {
                  <span class="text-kv-muted">Ninguno (todo el país)</span>
                }
              </dd>
            </div>
            @if (e.dropped) {
              <div class="sm:col-span-2">
                <dt class="eyebrow">Filtros descartados</dt>
                <dd class="text-xs text-amber-200">{{ e.dropped }} — el modelo los propuso pero la persona no los mencionó.</dd>
              </div>
            }
            <div><dt class="eyebrow">Resultados</dt><dd>{{ e.resultSize }}</dd></div>
            <div><dt class="eyebrow">Unidad de análisis</dt><dd>{{ e.unit }}</dd></div>
          </dl>
        </section>

        <section class="rounded-xl border border-kv-border bg-kv-bg/40 p-4" aria-labelledby="ev-summary">
          <h3 id="ev-summary" class="flex items-center gap-2 text-sm font-semibold">
            <lucide-icon [img]="quoteIcon" [size]="16" class="text-kv-violet" /> Resumen generado por Kognia
          </h3>
          @if (e.summary) {
            <blockquote class="mt-2 border-l-2 border-kv-violet/60 pl-3 text-sm text-kv-ink">{{ e.summary }}</blockquote>
            <p class="mt-2 text-[11px] text-kv-subtle">Texto redactado por el modelo a partir de los datos verificados. Ante una diferencia, prevalecen los datos.</p>
          } @else {
            <p class="mt-2 text-sm text-kv-muted">Aún no hay respuesta hablada asociada a esta consulta.</p>
          }
        </section>

        <section class="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4" aria-labelledby="ev-limits">
          <h3 id="ev-limits" class="flex items-center gap-2 text-sm font-semibold text-amber-200">
            <lucide-icon [img]="warnIcon" [size]="16" /> Limitaciones e interpretación
          </h3>
          <ul class="mt-2 space-y-1 text-sm text-amber-50/90">
            @for (note of e.limitations; track note) {
              <li>• {{ note }}</li>
            } @empty {
              <li class="text-kv-muted">La herramienta no reportó limitaciones adicionales.</li>
            }
          </ul>
        </section>

        @if (e.missing) {
          <section class="rounded-xl border border-kv-danger/40 bg-kv-danger/10 p-4 text-sm text-red-100" role="alert">
            <p class="flex items-center gap-2 font-semibold"><lucide-icon [img]="alertIcon" [size]="16" /> Falta de información</p>
            <p class="mt-1">{{ e.missing }}</p>
          </section>
        }
      </div>
    } @else {
      <p class="flex items-center gap-2 py-10 text-center text-sm text-kv-muted">
        <lucide-icon [img]="dbIcon" [size]="16" /> Cada respuesta con datos mostrará aquí su procedencia verificable.
      </p>
    }
  `,
})
export class EvidencePanelComponent {
  private readonly store = inject(ConversationStore);
  private readonly dashboard = inject(DashboardStateService);
  protected readonly verifiedIcon = BadgeCheck;
  protected readonly quoteIcon = MessageSquareQuote;
  protected readonly warnIcon = FileWarning;
  protected readonly alertIcon = CircleAlert;
  protected readonly dbIcon = Database;
  protected readonly zapIcon = Zap;

  protected readonly evidence = computed(() => {
    const q = this.dashboard.selectedQuery();
    if (!q) return null;
    const result = q.result as Record<string, unknown> | null;
    const meta = (result?.['metadata'] ?? (result?.['totals'] as Record<string, unknown> | undefined)?.['metadata']) as
      | QueryMetadata
      | undefined;
    const limitations = (result?.['limitations'] as string[] | undefined) ?? meta?.limitations ?? [];
    const filters = Object.entries(meta?.filters ?? {}).map(([k, v]) => ({ key: FILTER_LABELS[k] ?? k, value: v }));
    const started = new Date(q.startedAt).getTime();
    const summary = this.store
      .segments()
      .filter((s) => s.role === 'agent' && new Date(s.timestamp).getTime() >= started)
      .at(0)?.text;
    return {
      tool: TOOL_LABELS[q.tool],
      meta,
      cached: limitations.some((l) => l.includes(CACHE_MARKER)),
      filters,
      dropped: (q.arguments['filtros_descartados'] as string | undefined) ?? null,
      resultSize: resultSize(result),
      unit: unitFor(q.tool, result),
      limitations: limitations.filter((l) => !l.includes(CACHE_MARKER)),
      summary,
      missing:
        q.status === 'failed'
          ? (q.message ?? 'La consulta no pudo completarse; no hay cifras que mostrar.')
          : resultSize(result) === '0 elementos'
            ? 'La fuente no devolvió registros para estos filtros.'
            : null,
    };
  });
}

function resultSize(result: Record<string, unknown> | null): string {
  if (!result) return 'Sin resultado';
  if (Array.isArray(result['buckets'])) return `${(result['buckets'] as unknown[]).length} elementos`;
  if (Array.isArray(result['items'])) return `${result['total_sedes']} sedes (página de ${(result['items'] as unknown[]).length})`;
  if (Array.isArray(result['capacidades'])) return `${(result['capacidades'] as unknown[]).length} líneas de capacidad`;
  if ('prestadores' in result) return '1 conteo agregado';
  return '1 resultado';
}

function unitFor(tool: string, result: Record<string, unknown> | null): string {
  if (tool === 'group_ips' && result?.['metric_description']) return String(result['metric_description']);
  if (tool === 'search_ips') return 'sedes';
  if (tool === 'get_ips_details') return 'líneas de capacidad instalada de una sede';
  return 'prestadores únicos, sedes únicas y registros';
}
