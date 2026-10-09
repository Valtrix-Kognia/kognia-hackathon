import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { ElapsedTimePipe } from '../../shared/pipes/elapsed-time.pipe';
import { speakerColor } from '../../shared/utils/labels';

const MIN_WIDTH_PCT = 0.8;

/** Who spoke when: one lane per diarized speaker plus Kognia, on the session clock. */
@Component({
  selector: 'app-speaker-timeline',
  imports: [ElapsedTimePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (lanes().length) {
      <div class="space-y-1.5" role="list" aria-label="Línea temporal de intervenciones">
        @for (lane of lanes(); track lane.label) {
          <div class="grid grid-cols-[7.5rem_1fr] items-center gap-2" role="listitem">
            <span class="flex items-center gap-1.5 truncate text-[11px] text-kv-muted">
              <span class="h-2 w-2 shrink-0 rounded-full" [style.background]="lane.color"></span>{{ lane.label }}
            </span>
            <div class="relative h-3 rounded bg-kv-bg/70" [attr.aria-label]="lane.label + ': ' + lane.items.length + ' intervenciones'">
              @for (item of lane.items; track item.id) {
                <span
                  class="absolute inset-y-0 rounded-sm"
                  [style.left.%]="item.left"
                  [style.width.%]="item.width"
                  [style.background]="lane.color"
                  [style.opacity]="item.uncertain ? 0.45 : 0.9"
                  [class.ring-1]="item.uncertain"
                  [class.ring-amber-300]="item.uncertain"
                  [title]="(item.start | elapsedTime) + ' · ' + item.text + (item.uncertain ? ' (voces superpuestas o hablante incierto)' : '')"
                ></span>
              }
            </div>
          </div>
        }
        <div class="grid grid-cols-[7.5rem_1fr] text-[10px] text-kv-subtle">
          <span></span>
          <span class="flex justify-between tabular"><span>00:00</span><span>{{ duration() | elapsedTime }}</span></span>
        </div>
      </div>
    } @else {
      <p class="text-xs text-kv-muted">Las intervenciones aparecerán aquí a medida que se transcriban.</p>
    }
  `,
})
export class SpeakerTimelineComponent {
  private readonly store = inject(ConversationStore);

  protected readonly duration = computed(() =>
    Math.max(1000, ...this.store.segments().filter((s) => s.is_final).map((s) => s.end_ms)),
  );

  protected readonly lanes = computed(() => {
    const total = this.duration();
    const lanes = new Map<string, { label: string; color: string; items: { id: string; left: number; width: number; start: number; text: string; uncertain: boolean }[] }>();
    for (const s of this.store.segments()) {
      if (!s.is_final) continue;
      const lane = lanes.get(s.speaker_label) ?? { label: s.speaker_label, color: speakerColor(s.speaker_label), items: [] };
      lane.items.push({
        id: s.id,
        left: (s.start_ms / total) * 100,
        width: Math.max(MIN_WIDTH_PCT, ((s.end_ms - s.start_ms) / total) * 100),
        start: s.start_ms,
        text: s.text,
        uncertain: !!s.overlap_suspected || s.speaker_label === 'Hablante desconocido',
      });
      lanes.set(s.speaker_label, lane);
    }
    return [...lanes.values()].sort((a, b) => order(a.label) - order(b.label));
  });
}

function order(label: string): number {
  if (label === 'Kognia') return 0;
  const match = /Hablante (\d+)/.exec(label);
  return match ? Number(match[1]) : 99;
}
