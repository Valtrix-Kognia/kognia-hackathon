import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { LucideAngularModule, MessageCircleQuestion, RefreshCcw, ShieldCheck, VolumeX } from 'lucide-angular';
import { TurnMode } from '../../core/models/realtime-event.model';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { VoiceRoomService } from '../../core/services/voice-room.service';

const REASONS: Record<string, string> = {
  palabra_activacion: 'Respondiendo: se dijo “Kognia”',
  solo_palabra_activacion: 'Te escucho: haz tu pregunta',
  seguimiento: 'Respondiendo: pregunta de seguimiento',
  pregunta_sobre_ips: 'Respondiendo: pregunta clara sobre IPS',
  solicitud_consolidada: 'Respondiendo: solicitud unida (venía en varias partes)',
  solicitud_incompleta: 'Esperando el resto de la pregunta…',
  activacion_ambigua: 'Ignorado: “Kognia” no se reconoció con claridad',
  conversacion_abierta: 'Respondiendo',
  no_dirigido_a_kognia: 'Ignorado: no iba dirigido a Kognia',
  muletilla: 'Ignorado: expresión breve',
  transcripcion_vacia: 'Ignorado: sin texto reconocible',
  habla_superpuesta: 'Se pidió repetir: varias voces a la vez',
  baja_confianza: 'Se pidió repetir: audio poco claro',
};

@Component({
  selector: 'app-turn-mode-selector',
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="space-y-2">
      <div class="grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1" role="radiogroup" aria-label="Modo de turnos">
        @for (option of options; track option.mode) {
          <button
            type="button"
            role="radio"
            [attr.aria-checked]="store.turnMode() === option.mode"
            class="rounded-lg px-3 py-2 text-xs font-medium transition"
            [class]="store.turnMode() === option.mode ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
            (click)="select(option.mode)"
          >
            {{ option.label }}
          </button>
        }
      </div>
      <p class="text-xs text-slate-500">
        @if (store.turnMode() === 'wake_word') {
          Empieza con <strong>“Kognia, …”</strong> (también respondo preguntas claras sobre IPS). Las demás conversaciones se transcriben pero no se responden.
          Durante 8 s puedes hacer una pregunta de seguimiento sin repetirlo. Para interrumpir, di “Kognia”.
        } @else {
          Kognia responde a cualquier pregunta. Útil con una sola persona y poco ruido.
        }
      </p>
      @if (decision(); as d) {
        <p class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs {{ d.tone }}" aria-live="polite">
          <lucide-icon [img]="d.icon" [size]="14" /> {{ d.label }}
        </p>
      }
    </div>
  `,
})
export class TurnModeSelectorComponent {
  protected readonly store = inject(ConversationStore);
  private readonly room = inject(VoiceRoomService);

  protected readonly options: { mode: TurnMode; label: string }[] = [
    { mode: 'wake_word', label: 'Activación “Kognia”' },
    { mode: 'open', label: 'Conversación abierta' },
  ];

  protected readonly decision = computed(() => {
    const d = this.store.lastDecision();
    if (!d) return null;
    const label = REASONS[d.reason] ?? d.reason;
    if (d.action === 'respond') return { label, icon: ShieldCheck, tone: 'bg-emerald-50 text-emerald-700' };
    if (d.action === 'ask_repeat') return { label, icon: RefreshCcw, tone: 'bg-amber-50 text-amber-800' };
    if (d.action === 'hold' || d.action === 'listen') return { label, icon: MessageCircleQuestion, tone: 'bg-sky-50 text-sky-800' };
    return { label, icon: d.reason === 'no_dirigido_a_kognia' ? VolumeX : MessageCircleQuestion, tone: 'bg-slate-100 text-slate-600' };
  });

  protected select(mode: TurnMode): void {
    void this.room.setTurnMode(mode);
  }
}
