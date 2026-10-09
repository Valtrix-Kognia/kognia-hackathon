import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  afterRenderEffect,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { ArrowDown, LucideAngularModule, MessageSquareText, Users } from 'lucide-angular';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { ElapsedTimePipe } from '../../shared/pipes/elapsed-time.pipe';
import { EMOTION_META } from '../../shared/utils/labels';
import { SpeakerBadgeComponent } from './speaker-badge.component';

const STICKY_THRESHOLD_PX = 80;

@Component({
  selector: 'app-transcript-timeline',
  imports: [LucideAngularModule, SpeakerBadgeComponent, ElapsedTimePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card flex h-full min-h-[24rem] flex-col" aria-labelledby="transcript-title">
      <header class="card-header">
        <h2 id="transcript-title" class="card-title">
          <lucide-icon [img]="titleIcon" [size]="16" class="text-brand-600" /> Transcripción en vivo
        </h2>
        <span class="chip bg-slate-100 text-slate-600" [title]="'Hablantes humanos distinguidos por diarización acústica'">
          <lucide-icon [img]="usersIcon" [size]="12" /> {{ speakerCount() }} hablante(s)
        </span>
      </header>

      <div class="relative flex-1">
        <ol
          #scroller
          class="absolute inset-0 space-y-3 overflow-y-auto px-5 py-4"
          (scroll)="onScroll()"
          aria-live="polite"
          aria-relevant="additions"
        >
          @for (segment of store.segments(); track segment.id) {
            <li class="flex gap-3" [class.flex-row-reverse]="segment.role === 'agent'">
              <div class="min-w-0 max-w-[85%]">
                <div class="mb-1 flex items-center gap-2 text-xs text-slate-500" [class.justify-end]="segment.role === 'agent'">
                  <app-speaker-badge [label]="segment.speaker_label" />
                  <time class="tabular-nums">{{ segment.start_ms | elapsedTime }}</time>
                  @if (!segment.is_final) {
                    <span class="italic text-slate-400">transcribiendo…</span>
                  }
                  @if (segment.interrupted) {
                    <span class="chip bg-amber-50 text-amber-700">interrumpido</span>
                  }
                  @if (emotionFor(segment.id); as emotion) {
                    <span class="chip {{ emotionChip(emotion) }}" title="Emoción estimada a partir del texto">{{ emotionLabel(emotion) }}</span>
                  }
                </div>
                <p
                  class="rounded-2xl px-3.5 py-2 text-sm leading-relaxed"
                  [class]="
                    segment.role === 'agent'
                      ? 'rounded-tr-sm bg-brand-700 text-white'
                      : segment.is_final
                        ? 'rounded-tl-sm bg-slate-100 text-slate-800'
                        : 'rounded-tl-sm border border-dashed border-slate-300 bg-white text-slate-500'
                  "
                >
                  {{ segment.text }}
                </p>
              </div>
            </li>
          } @empty {
            <li class="flex h-full flex-col items-center justify-center gap-2 py-12 text-center text-sm text-slate-400">
              <lucide-icon [img]="titleIcon" [size]="28" />
              La transcripción aparecerá aquí cuando empiece la conversación.
            </li>
          }
        </ol>

        @if (!stickToBottom() && store.segments().length) {
          <button
            type="button"
            class="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full bg-brand-700 px-3 py-1.5 text-xs font-medium text-white shadow-lg"
            (click)="scrollToBottom()"
          >
            <lucide-icon [img]="downIcon" [size]="14" /> Ir a lo más reciente
          </button>
        }
      </div>
    </section>
  `,
})
export class TranscriptTimelineComponent {
  protected readonly store = inject(ConversationStore);
  protected readonly titleIcon = MessageSquareText;
  protected readonly usersIcon = Users;
  protected readonly downIcon = ArrowDown;
  protected readonly stickToBottom = signal(true);

  private readonly scroller = viewChild.required<ElementRef<HTMLElement>>('scroller');

  protected readonly speakerCount = computed(() => this.store.speakers().size);

  constructor() {
    afterRenderEffect(() => {
      this.store.segments();
      if (this.stickToBottom()) this.scrollToBottom();
    });
  }

  protected emotionFor(segmentId: string) {
    const analysis = this.store.emotionBySegment().get(segmentId);
    return analysis?.status === 'ok' && analysis.emotion ? analysis.emotion : null;
  }

  protected emotionLabel(emotion: keyof typeof EMOTION_META): string {
    return EMOTION_META[emotion].label;
  }

  protected emotionChip(emotion: keyof typeof EMOTION_META): string {
    return EMOTION_META[emotion].chip;
  }

  protected onScroll(): void {
    const el = this.scroller().nativeElement;
    this.stickToBottom.set(el.scrollHeight - el.scrollTop - el.clientHeight < STICKY_THRESHOLD_PX);
  }

  protected scrollToBottom(): void {
    const el = this.scroller().nativeElement;
    el.scrollTop = el.scrollHeight;
    this.stickToBottom.set(true);
  }
}
