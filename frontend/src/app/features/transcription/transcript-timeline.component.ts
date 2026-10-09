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
import { ArrowDown, Check, LucideAngularModule, MessageSquareText, Pencil, Users, X } from 'lucide-angular';
import { TranscriptSegment } from '../../core/models/realtime-event.model';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { ElapsedTimePipe } from '../../shared/pipes/elapsed-time.pipe';
import { EMOTION_META } from '../../shared/utils/labels';
import { SpeakerBadgeComponent } from './speaker-badge.component';
import { SpeakerTimelineComponent } from './speaker-timeline.component';

const STICKY_THRESHOLD_PX = 80;

@Component({
  selector: 'app-transcript-timeline',
  imports: [LucideAngularModule, SpeakerBadgeComponent, SpeakerTimelineComponent, ElapsedTimePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card flex h-full min-h-[28rem] flex-col" aria-labelledby="transcript-title">
      <header class="card-header">
        <h2 id="transcript-title" class="card-title">
          <lucide-icon [img]="titleIcon" [size]="16" class="text-kv-accent" /> Transcripción en vivo
        </h2>
        <span class="chip chip-neutral" title="Voces distinguidas por diarización acústica (no identifican personas)">
          <lucide-icon [img]="usersIcon" [size]="12" /> {{ speakerCount() }} voz(es)
        </span>
      </header>

      <div class="border-b border-kv-border px-5 py-3">
        <app-speaker-timeline />
      </div>

      <div class="relative min-h-0 flex-1">
        <ol
          #scroller
          class="absolute inset-0 space-y-3 overflow-y-auto px-5 py-4"
          (scroll)="onScroll()"
          aria-live="polite"
          aria-relevant="additions"
        >
          @for (segment of store.segments(); track segment.id) {
            <li class="fade-in flex" [class.justify-end]="segment.role === 'agent'">
              <div class="min-w-0 max-w-[88%]">
                <div class="mb-1 flex flex-wrap items-center gap-1.5 text-[11px] text-kv-muted" [class.justify-end]="segment.role === 'agent'">
                  <app-speaker-badge [label]="segment.speaker_label" />
                  <time class="tabular">{{ segment.start_ms | elapsedTime }}</time>
                  @if (!segment.is_final) {
                    <span class="italic text-kv-subtle">transcribiendo…</span>
                  }
                  @if (segment.overlap_suspected) {
                    <span class="chip bg-orange-400/15 text-orange-200 ring-1 ring-orange-400/30" title="Varias voces a la vez: la atribución puede ser imprecisa">voces superpuestas</span>
                  }
                  @if (segment.speaker_label === 'Hablante desconocido') {
                    <span class="chip chip-neutral" title="El sistema no atribuyó este fragmento a una voz">incierto</span>
                  }
                  @if (segment.interrupted) {
                    <span class="chip bg-amber-400/15 text-amber-200 ring-1 ring-amber-400/30">interrumpido</span>
                  }
                  @if (emotionFor(segment.id); as emotion) {
                    <span class="chip {{ emotionChip(emotion) }}" title="Emoción estimada a partir del texto">{{ emotionLabel(emotion) }}</span>
                  }
                </div>

                @if (editing() === segment.id) {
                  <form class="flex gap-1.5" (submit)="$event.preventDefault(); saveCorrection(segment.id)">
                    <label class="sr-only" [attr.for]="'fix-' + segment.id">Corrección de la transcripción</label>
                    <input
                      [id]="'fix-' + segment.id"
                      class="min-w-0 flex-1 rounded-lg border border-kv-accent/50 bg-kv-bg px-3 py-1.5 text-sm text-kv-ink"
                      [value]="draft()"
                      (input)="draft.set($any($event.target).value)"
                      (keydown.escape)="editing.set(null)"
                    />
                    <button type="submit" class="btn-primary !px-2.5 !py-1.5" aria-label="Guardar corrección"><lucide-icon [img]="checkIcon" [size]="14" /></button>
                    <button type="button" class="btn-ghost !px-2.5 !py-1.5" aria-label="Cancelar" (click)="editing.set(null)"><lucide-icon [img]="closeIcon" [size]="14" /></button>
                  </form>
                } @else {
                  <div class="group relative">
                    <p
                      class="rounded-2xl px-3.5 py-2 text-sm leading-relaxed"
                      [class]="bubbleClass(segment)"
                    >
                      {{ corrections().get(segment.id) ?? segment.text }}
                    </p>
                    @if (corrections().has(segment.id)) {
                      <p class="mt-1 text-[11px] text-kv-subtle">
                        <span class="chip chip-neutral mr-1">corregido</span>
                        Original: <span class="line-through">{{ segment.text }}</span>
                      </p>
                    }
                    @if (segment.role === 'user' && segment.is_final && segment.speaker_id !== 'texto') {
                      <button
                        type="button"
                        class="absolute -right-2 -top-2 hidden rounded-full bg-kv-elevated p-1.5 text-kv-muted ring-1 ring-kv-border hover:text-kv-ink group-hover:block focus-visible:block"
                        [attr.aria-label]="'Corregir transcripción de ' + segment.speaker_label"
                        (click)="startEditing(segment)"
                      >
                        <lucide-icon [img]="editIcon" [size]="12" />
                      </button>
                    }
                  </div>
                }
              </div>
            </li>
          } @empty {
            <li class="flex h-full flex-col items-center justify-center gap-2 py-12 text-center text-sm text-kv-muted">
              <lucide-icon [img]="titleIcon" [size]="28" />
              La transcripción aparecerá aquí cuando empiece la conversación.
            </li>
          }
        </ol>

        @if (!stickToBottom() && store.segments().length) {
          <button
            type="button"
            class="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full bg-kv-primary px-3 py-1.5 text-xs font-medium text-white shadow-lg"
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
  protected readonly editIcon = Pencil;
  protected readonly checkIcon = Check;
  protected readonly closeIcon = X;
  protected readonly stickToBottom = signal(true);
  protected readonly editing = signal<string | null>(null);
  protected readonly draft = signal('');
  protected readonly corrections = this.store.corrections;

  private readonly scroller = viewChild.required<ElementRef<HTMLElement>>('scroller');

  protected readonly speakerCount = computed(() => this.store.speakers().size);

  constructor() {
    afterRenderEffect(() => {
      this.store.segments();
      if (this.stickToBottom()) this.scrollToBottom();
    });
  }

  protected bubbleClass(segment: TranscriptSegment): string {
    if (segment.role === 'agent') return 'rounded-tr-sm bg-kv-violet/15 text-kv-ink ring-1 ring-kv-violet/30';
    if (!segment.is_final) return 'rounded-tl-sm border border-dashed border-kv-border-strong text-kv-muted';
    return 'rounded-tl-sm bg-kv-elevated text-kv-ink ring-1 ring-kv-border';
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

  protected startEditing(segment: TranscriptSegment): void {
    this.draft.set(this.corrections().get(segment.id) ?? segment.text);
    this.editing.set(segment.id);
  }

  protected saveCorrection(segmentId: string): void {
    this.store.setCorrection(segmentId, this.draft());
    this.editing.set(null);
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
