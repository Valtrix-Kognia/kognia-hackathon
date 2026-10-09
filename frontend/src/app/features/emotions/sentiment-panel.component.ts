import { LowerCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Brain, Info, LucideAngularModule } from 'lucide-angular';
import { Sentiment } from '../../core/models/realtime-event.model';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { EMOTION_META, SENTIMENT_META } from '../../shared/utils/labels';
import { EmotionTimelineComponent } from './emotion-timeline.component';

const SENTIMENTS: Sentiment[] = ['positivo', 'neutral', 'negativo'];

@Component({
  selector: 'app-sentiment-panel',
  imports: [LucideAngularModule, EmotionTimelineComponent, LowerCasePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card" aria-labelledby="cognitive-title">
      <header class="card-header">
        <h2 id="cognitive-title" class="card-title">
          <lucide-icon [img]="brainIcon" [size]="16" class="text-kv-accent" /> Panel cognitivo
        </h2>
        <span class="text-xs text-kv-subtle">{{ classified().length }} intervención(es)</span>
      </header>

      <div class="space-y-5 p-5">
        <div>
          <p class="mb-2 text-xs font-medium uppercase tracking-wide text-kv-muted">Emoción estimada · último segmento</p>
          @if (latest(); as last) {
            @if (last.status === 'ok' && last.emotion && last.sentiment) {
              <div class="flex flex-wrap items-center gap-2">
                <span class="chip text-sm {{ emotionMeta[last.emotion].chip }}">{{ emotionMeta[last.emotion].label }}</span>
                <span class="chip text-sm bg-kv-surface ring-1 ring-kv-border {{ sentimentMeta[last.sentiment].text }}">
                  Sentimiento {{ sentimentMeta[last.sentiment].label | lowercase }}
                </span>
                <span class="text-xs text-kv-muted">
                  {{ last.speaker_label }} · confianza del modelo {{ percent(last.emotion_score) }}
                  @if (last.low_confidence) {
                    <span class="text-amber-600">(baja)</span>
                  }
                </span>
              </div>
            } @else if (last.status === 'texto_insuficiente') {
              <p class="text-sm text-kv-muted">Texto demasiado corto para estimar emoción.</p>
            } @else {
              <p class="text-sm text-rose-600">No fue posible clasificar el último segmento.</p>
            }
          } @else {
            <div class="skeleton h-7 w-48" aria-hidden="true"></div>
            <p class="mt-2 text-xs text-kv-subtle">Se analiza cada intervención final del usuario.</p>
          }
        </div>

        <div>
          <p class="mb-2 text-xs font-medium uppercase tracking-wide text-kv-muted">Distribución de sentimiento</p>
          <div class="flex h-2.5 overflow-hidden rounded-full bg-kv-elevated" role="img" [attr.aria-label]="distributionLabel()">
            @for (item of distribution(); track item.key) {
              <div class="{{ sentimentMeta[item.key].bar }} transition-all" [style.width.%]="item.pct"></div>
            }
          </div>
          <ul class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-kv-muted">
            @for (item of distribution(); track item.key) {
              <li class="flex items-center gap-1.5">
                <span class="size-2 rounded-full {{ sentimentMeta[item.key].dot }}"></span>
                {{ sentimentMeta[item.key].label }} · {{ item.count }}
              </li>
            }
          </ul>
        </div>

        <app-emotion-timeline [items]="classified()" />

        <p class="flex gap-2 rounded-lg bg-kv-elevated px-3 py-2 text-xs text-kv-muted">
          <lucide-icon [img]="infoIcon" [size]="14" class="mt-0.5 shrink-0" />
          Estimación automática a partir del texto transcrito (modelos RoBERTuito de pysentimiento). No analiza el tono de voz ni
          constituye una evaluación psicológica.
        </p>
      </div>
    </section>
  `,
})
export class SentimentPanelComponent {
  private readonly store = inject(ConversationStore);
  protected readonly brainIcon = Brain;
  protected readonly infoIcon = Info;
  protected readonly emotionMeta = EMOTION_META;
  protected readonly sentimentMeta = SENTIMENT_META;

  protected readonly classified = computed(() => this.store.emotions().filter((e) => e.status === 'ok'));
  protected readonly latest = computed(() => this.store.emotions().at(-1) ?? null);
  protected readonly distribution = computed(() => {
    const items = this.classified();
    const total = items.length || 1;
    return SENTIMENTS.map((key) => {
      const count = items.filter((e) => e.sentiment === key).length;
      return { key, count, pct: (count / total) * 100 };
    });
  });
  protected readonly distributionLabel = computed(() =>
    this.distribution()
      .map((d) => `${SENTIMENT_META[d.key].label}: ${d.count}`)
      .join(', '),
  );

  protected percent(score: number | null): string {
    return score == null ? 'n/d' : `${Math.round(score * 100)} %`;
  }
}
