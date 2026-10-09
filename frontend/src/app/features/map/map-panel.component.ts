import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { LucideAngularModule, MapPin, RotateCcw, Sparkles, TriangleAlert } from 'lucide-angular';
import { formatNumber } from '../../shared/utils/labels';
import { quantileClasses } from './choropleth-scale';
import { ColombiaMapComponent } from './colombia-map.component';
import { ISO_NAMES } from './department-catalog';
import { MapStateService } from './map-state.service';

const NATURALEZAS = ['Pública', 'Privada', 'Mixta'];

@Component({
  selector: 'app-map-panel',
  imports: [LucideAngularModule, ColombiaMapComponent, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
      <div>
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <div class="flex rounded-xl bg-kv-bg/60 p-1 ring-1 ring-kv-border" role="radiogroup" aria-label="Métrica del mapa">
            @for (m of metrics; track m.value) {
              <button
                type="button"
                role="radio"
                class="tab"
                [class.tab-active]="state.context().metric === m.value"
                [attr.aria-checked]="state.context().metric === m.value"
                (click)="state.setMetric(m.value)"
              >
                {{ m.label }}
              </button>
            }
          </div>
          <label class="flex items-center gap-2 text-xs text-kv-muted">
            Naturaleza
            <select
              class="rounded-lg border border-kv-border bg-kv-elevated px-2 py-1.5 text-sm text-kv-ink"
              [value]="state.context().naturaleza ?? ''"
              (change)="state.setNaturaleza($any($event.target).value || null)"
            >
              <option value="">Todas</option>
              @for (n of naturalezas; track n) {
                <option [value]="n">{{ n }}</option>
              }
            </select>
          </label>
          @if (state.selectedIso()) {
            <button type="button" class="btn-ghost !px-3 !py-1.5 text-xs" (click)="state.select(null)">
              <lucide-icon [img]="resetIcon" [size]="14" /> Restablecer
            </button>
          }
        </div>

        @if (state.context().origin === 'respuesta_kognia') {
          <p class="mb-3 flex items-center gap-2 rounded-lg bg-kv-accent/10 px-3 py-2 text-xs text-cyan-100 ring-1 ring-kv-accent/30">
            <lucide-icon [img]="sparkIcon" [size]="14" />
            Actualizado por la última respuesta de Kognia. Los departamentos que mencionó tienen borde cian.
          </p>
        }

        @switch (state.dataState()) {
          @case ('error') {
            <div class="flex items-center gap-2 rounded-xl border border-kv-danger/40 bg-kv-danger/10 p-4 text-sm text-red-200" role="alert">
              <lucide-icon [img]="alertIcon" [size]="16" /> No fue posible cargar los datos oficiales del mapa. No se muestran valores.
            </div>
          }
          @default {
            @if (state.aggregated(); as agg) {
              <app-colombia-map
                [values]="agg.values"
                [classes]="classes()"
                [highlighted]="state.context().highlighted"
                [selectedIso]="state.selectedIso()"
                [unitLabel]="unitLabel()"
                (selected)="state.select($event)"
                [class.opacity-60]="state.dataState() === 'loading'"
              />
            } @else {
              <div class="skeleton aspect-[7/8] w-full" aria-busy="true"></div>
            }
          }
        }

        <div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-kv-muted" aria-label="Leyenda">
          <span class="font-medium text-kv-ink">{{ unitLabel() }}:</span>
          @for (c of classes(); track c.min) {
            <span class="flex items-center gap-1">
              <span class="inline-block h-3 w-5 rounded-sm" [style.background]="c.color"></span>
              <span class="tabular">{{ fmt(c.min) }}–{{ fmt(c.max) }}</span>
            </span>
          }
          <span class="flex items-center gap-1">
            <svg width="20" height="12" aria-hidden="true"><rect width="20" height="12" rx="2" fill="url(#kv-no-data)" /></svg>
            Sin datos
          </span>
        </div>
      </div>

      <aside class="space-y-4" aria-live="polite">
        @if (state.selectedIso(); as iso) {
          <div class="fade-in rounded-xl border border-kv-border bg-kv-elevated/50 p-4">
            <p class="eyebrow flex items-center gap-1.5"><lucide-icon [img]="pinIcon" [size]="12" /> Departamento seleccionado</p>
            <h3 class="mt-1 text-lg font-semibold">{{ names[iso] }}</h3>
            @switch (state.statsState()) {
              @case ('loading') {
                <div class="mt-3 space-y-2"><div class="skeleton h-14"></div><div class="skeleton h-24"></div></div>
              }
              @case ('error') {
                <p class="mt-3 text-sm text-red-200" role="alert">No se pudieron consultar las estadísticas oficiales.</p>
              }
              @default {
                @if (state.selectedStats().length) {
                  <table class="mt-3 w-full text-sm">
                    <caption class="sr-only">Conteos oficiales por fila del dataset</caption>
                    <thead class="text-left text-[11px] uppercase tracking-wide text-kv-muted">
                      <tr><th class="py-1 pr-2 font-medium">Fila en la fuente</th><th class="py-1 pl-3 text-right font-medium">Prestadores</th><th class="py-1 pl-3 text-right font-medium">Sedes</th><th class="py-1 pl-3 text-right font-medium">Registros</th></tr>
                    </thead>
                    <tbody class="tabular divide-y divide-kv-border">
                      @for (s of state.selectedStats(); track s.label) {
                        <tr>
                          <td class="py-1.5">{{ s.label }}</td>
                          <td class="py-1.5 pl-3 text-right">{{ fmt(s.result.prestadores) }}</td>
                          <td class="py-1.5 pl-3 text-right">{{ fmt(s.result.sedes) }}</td>
                          <td class="py-1.5 pl-3 text-right">{{ fmt(s.result.registros) }}</td>
                        </tr>
                      }
                    </tbody>
                  </table>
                  @if (state.selectedStats().length > 1) {
                    <p class="mt-2 text-xs text-kv-muted">
                      El dataset reporta distritos por separado. Sedes y registros se pueden sumar
                      ({{ fmt(totalSedes()) }} sedes); los prestadores no, porque uno puede operar en ambos.
                    </p>
                  }
                  @if (state.naturalezaBreakdown(); as nb) {
                    <p class="eyebrow mt-4">Sedes por naturaleza · {{ state.selectedStats()[0].label }}</p>
                    <ul class="mt-2 space-y-1.5">
                      @for (b of nb.buckets; track b.label) {
                        <li class="grid grid-cols-[5rem_1fr_3.5rem] items-center gap-2 text-sm">
                          <span class="text-kv-muted">{{ b.label }}</span>
                          <span class="h-2 rounded-full bg-kv-bg"><span class="block h-2 rounded-full bg-[var(--kv-series-1)]" [style.width.%]="(b.value / maxBucket(nb.buckets)) * 100"></span></span>
                          <span class="tabular text-right">{{ fmt(b.value) }}</span>
                        </li>
                      }
                    </ul>
                  }
                } @else {
                  <p class="mt-3 text-sm text-kv-muted">La fuente no registra sedes para este departamento con el filtro actual.</p>
                }
              }
            }
            <p class="mt-3 text-[11px] text-kv-subtle">
              Las preguntas por voz no heredan esta selección: menciona el departamento al hablar con Kognia.
            </p>
          </div>
        } @else {
          <div class="rounded-xl border border-dashed border-kv-border p-4 text-sm text-kv-muted">
            Selecciona un departamento (clic o Enter) para ver sus cifras oficiales. Esc o “Restablecer” vuelve a la vista nacional.
          </div>
        }

        <div class="space-y-2 rounded-xl bg-kv-bg/50 p-4 text-xs text-kv-muted ring-1 ring-kv-border">
          <p class="eyebrow">Cómo leer el mapa</p>
          <p>Color en 6 clases por cuantiles de {{ unitLabel() }} (la distribución es muy desigual). Los prestadores únicos no se mapean porque no son sumables entre territorios.</p>
          @if (state.aggregated()?.districtsMerged?.length) {
            <p>Distritos sumados a su departamento: {{ state.aggregated()!.districtsMerged.join(', ') }}.</p>
          }
          @if (state.aggregated()?.unmatched?.length) {
            <p class="text-amber-200">Valores sin polígono: {{ unmatchedText() }}.</p>
          }
          @if (state.metadata(); as meta) {
            <p>Fuente: datos.gov.co · {{ meta.dataset_id }} · consultado {{ meta.queried_at | date: 'HH:mm' }}</p>
          }
          <p>Límites: geoBoundaries (OpenStreetMap, ODbL 1.0), simplificados.</p>
        </div>
      </aside>
    </div>
  `,
})
export class MapPanelComponent {
  protected readonly state = inject(MapStateService);
  protected readonly names = ISO_NAMES;
  protected readonly naturalezas = NATURALEZAS;
  protected readonly fmt = formatNumber;
  protected readonly resetIcon = RotateCcw;
  protected readonly sparkIcon = Sparkles;
  protected readonly alertIcon = TriangleAlert;
  protected readonly pinIcon = MapPin;
  protected readonly metrics = [
    { value: 'sedes' as const, label: 'Sedes' },
    { value: 'registros' as const, label: 'Registros' },
  ];

  protected readonly unitLabel = computed(() => (this.state.context().metric === 'sedes' ? 'sedes únicas' : 'registros'));
  protected readonly classes = computed(() => {
    const values = this.state.aggregated()?.values;
    return values ? quantileClasses([...values.values()].map((v) => v.value)) : [];
  });
  protected readonly totalSedes = computed(() =>
    this.state.selectedStats().reduce((sum, s) => sum + s.result.sedes, 0),
  );
  protected readonly unmatchedText = computed(() =>
    (this.state.aggregated()?.unmatched ?? []).map((u) => `${u.label} (${formatNumber(u.value)})`).join(', '),
  );

  constructor() {
    this.state.ensureLoaded();
  }

  protected maxBucket(buckets: { value: number }[]): number {
    return Math.max(1, ...buckets.map((b) => b.value));
  }
}
