import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { EmotionAnalysis } from '../../core/models/realtime-event.model';
import { EMOTION_META, SENTIMENT_META } from '../../shared/utils/labels';

@Component({
  selector: 'app-emotion-timeline',
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div>
      <p class="mb-2 text-xs font-medium uppercase tracking-wide text-kv-muted">Evolución de la sesión</p>
      @if (items().length) {
        <ol class="flex items-end gap-1.5 overflow-x-auto pb-1" aria-label="Línea de tiempo emocional">
          @for (item of items(); track item.segment_id) {
            <li class="group relative flex flex-col items-center">
              <span
                class="w-5 rounded-t-md {{ sentiment[item.sentiment!].bar }}"
                [style.height.px]="8 + (item.sentiment_score ?? 0) * 40"
                [style.opacity]="item.low_confidence ? 0.45 : 1"
              ></span>
              <span class="mt-1 text-[10px] text-kv-subtle">{{ $index + 1 }}</span>
              <span
                class="pointer-events-none absolute bottom-full z-10 mb-1 hidden w-max max-w-48 rounded-md bg-kv-bg px-2 py-1 text-[11px] text-white group-hover:block"
              >
                {{ item.speaker_label }} · {{ emotion[item.emotion!].label }} · {{ sentiment[item.sentiment!].label }} ·
                {{ item.analyzed_at | date: 'HH:mm:ss' }}
              </span>
            </li>
          }
        </ol>
      } @else {
        <p class="text-sm text-kv-subtle">Aún no hay intervenciones clasificadas.</p>
      }
    </div>
  `,
})
export class EmotionTimelineComponent {
  readonly items = input.required<EmotionAnalysis[]>();
  protected readonly emotion = EMOTION_META;
  protected readonly sentiment = SENTIMENT_META;
}
