import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Gauge, LucideAngularModule } from 'lucide-angular';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { percentile } from '../../shared/utils/stats';

const STAGES: { key: 'end_of_turn_delay' | 'transcription_delay' | 'llm_node_ttft' | 'tts_node_ttfb'; label: string; color: string }[] = [
  { key: 'end_of_turn_delay', label: 'Fin de turno', color: 'bg-slate-400' },
  { key: 'transcription_delay', label: 'Transcripción', color: 'bg-sky-400' },
  { key: 'llm_node_ttft', label: 'LLM 1er token', color: 'bg-violet-400' },
  { key: 'tts_node_ttfb', label: 'TTS 1er audio', color: 'bg-amber-400' },
];

@Component({
  selector: 'app-latency-panel',
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card" aria-labelledby="latency-title">
      <header class="card-header">
        <h2 id="latency-title" class="card-title">
          <lucide-icon [img]="icon" [size]="16" class="text-brand-600" /> Latencia
        </h2>
        <span class="text-xs text-slate-400">{{ store.latencyTurns().length }} turno(s) medidos</span>
      </header>
      <div class="space-y-4 p-5">
        <dl class="grid grid-cols-3 gap-3 text-center">
          @for (kpi of kpis(); track kpi.label) {
            <div class="rounded-xl bg-slate-50 p-2.5 ring-1 ring-slate-100">
              <dt class="text-[11px] leading-tight text-slate-500">{{ kpi.label }}</dt>
              <dd class="mt-1 text-sm font-semibold tabular-nums text-slate-900">{{ kpi.value }}</dd>
            </div>
          }
        </dl>

        @if (last(); as turn) {
          <div>
            <p class="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
              Último turno · <span class="font-mono normal-case">{{ turn.turn_id }}</span>
              @if (browserForLast(); as b) {
                · navegador {{ b }}
              }
            </p>
            <ul class="space-y-1.5 text-xs">
              @for (stage of lastStages(); track stage.label) {
                <li class="grid grid-cols-[7.5rem_1fr_4rem] items-center gap-2">
                  <span class="text-slate-600">{{ stage.label }}</span>
                  <span class="h-1.5 rounded-full bg-slate-100">
                    <span class="block h-1.5 rounded-full {{ stage.color }}" [style.width.%]="stage.pct"></span>
                  </span>
                  <span class="text-right tabular-nums text-slate-700">{{ stage.ms }} ms</span>
                </li>
              }
            </ul>
          </div>
        } @else {
          <p class="text-sm text-slate-400">Las métricas aparecen después de la primera respuesta.</p>
        }
        <p class="text-[11px] text-slate-400">
          Etapas medidas en el agente con relojes del propio proceso. “Reproducción en navegador” se mide en este equipo desde la
          decisión de turno hasta que el agente se escucha, e incluye la red.
        </p>
      </div>
    </section>
  `,
})
export class LatencyPanelComponent {
  protected readonly store = inject(ConversationStore);
  protected readonly icon = Gauge;

  protected readonly last = computed(() => this.store.latencyTurns().at(-1) ?? null);

  protected readonly kpis = computed(() => {
    const summary = this.last()?.summary;
    const browser = [...this.store.browserPlaybackMs()];
    const fmt = (v: number | null | undefined) => (v == null ? '—' : `${(v / 1000).toFixed(2)} s`);
    return [
      { label: 'Primer audio p50 / p95', value: `${fmt(summary?.first_audio_p50_ms)} / ${fmt(summary?.first_audio_p95_ms)}` },
      { label: 'Respuesta p50 / p95', value: `${fmt(summary?.e2e_p50_ms)} / ${fmt(summary?.e2e_p95_ms)}` },
      { label: 'Reproducción en navegador p50', value: fmt(percentile(browser, 50)) },
    ];
  });

  protected readonly browserForLast = computed(() => {
    const turn = this.last();
    if (!turn) return null;
    const m = this.store.playback().find((p) => p.turn_id === turn.turn_id);
    if (!m) return null;
    return m.status === 'medido' ? `${m.decision_to_audible_ms} ms` : 'reemplazado';
  });

  protected readonly lastStages = computed(() => {
    const turn = this.last();
    if (!turn) return [];
    const rows = [
      ...STAGES.map((s) => ({ label: s.label, color: s.color, ms: turn.stages_ms[s.key] })),
      { label: 'Socrata', color: 'bg-emerald-400', ms: turn.tools.length ? turn.socrata_ms : undefined },
      { label: 'Total hasta respuesta', color: 'bg-brand-500', ms: turn.stages_ms.e2e_latency },
    ].filter((r): r is { label: string; color: string; ms: number } => typeof r.ms === 'number');
    const max = Math.max(1, ...rows.map((r) => r.ms));
    return rows.map((r) => ({ ...r, ms: Math.round(r.ms), pct: (r.ms / max) * 100 }));
  });
}
