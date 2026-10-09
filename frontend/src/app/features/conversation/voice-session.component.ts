import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import {
  AudioLines,
  CircleAlert,
  Database,
  Ear,
  Loader,
  LucideAngularModule,
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  PowerOff,
  RotateCw,
  Send,
  Sparkles,
  Volume2,
} from 'lucide-angular';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { PreferencesService } from '../../core/services/preferences.service';
import { VoiceRoomService } from '../../core/services/voice-room.service';
import { TurnModeSelectorComponent } from './turn-mode-selector.component';
import { VoiceOrbComponent } from './voice-orb.component';

type OrbState =
  | 'desconectado'
  | 'conectando'
  | 'escuchando'
  | 'usuario_hablando'
  | 'procesando'
  | 'consultando'
  | 'respondiendo'
  | 'error';

const STATES: Record<OrbState, { label: string; hint: string; icon: typeof Ear; tone: string }> = {
  desconectado: { label: 'Desconectado', hint: 'Inicia una conversación para hablar con Kognia', icon: PowerOff, tone: 'text-kv-muted' },
  conectando: { label: 'Conectando', hint: 'Preparando la sala de voz segura', icon: Loader, tone: 'text-amber-300' },
  escuchando: { label: 'Escuchando', hint: 'Haz tu pregunta con naturalidad', icon: Ear, tone: 'text-emerald-300' },
  usuario_hablando: { label: 'Te escucho', hint: 'Transcribiendo en vivo', icon: Mic, tone: 'text-cyan-300' },
  procesando: { label: 'Procesando', hint: 'Interpretando la pregunta', icon: Sparkles, tone: 'text-blue-300' },
  consultando: { label: 'Consultando datos', hint: 'API oficial datos.gov.co', icon: Database, tone: 'text-violet-300' },
  respondiendo: { label: 'Kognia responde', hint: 'Puedes interrumpir hablando', icon: AudioLines, tone: 'text-violet-200' },
  error: { label: 'Sin conexión', hint: 'Reconecta para continuar', icon: CircleAlert, tone: 'text-red-300' },
};

@Component({
  selector: 'app-voice-session',
  imports: [LucideAngularModule, VoiceOrbComponent, TurnModeSelectorComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card overflow-hidden" aria-labelledby="voice-title">
      <div class="relative px-5 pb-4 pt-5">
        <h2 id="voice-title" class="sr-only">Conversación por voz</h2>
        <app-voice-orb
          [micTrack]="room.localTrack()"
          [agentTrack]="room.agentTrack()"
          [active]="active()"
          [tone]="orbTone()"
          (userSpeaking)="userSpeaking.set($event)"
        />
        <div class="mt-2 text-center" role="status" aria-live="polite">
          <p class="flex items-center justify-center gap-2 text-base font-semibold {{ state().tone }}">
            <lucide-icon [img]="state().icon" [size]="18" [class.animate-spin]="orbState() === 'conectando'" />
            {{ state().label }}
          </p>
          <p class="mt-0.5 text-xs text-kv-muted">{{ state().hint }}</p>
        </div>
        <div class="mt-3 flex items-center justify-center gap-4 text-[11px] text-kv-subtle" aria-hidden="true">
          <span class="flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-kv-accent"></span> Tu micrófono</span>
          <span class="flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-kv-violet"></span> Voz de Kognia</span>
        </div>

        @if (prefs.captions() && store.agentLive(); as live) {
          <p class="fade-in mt-4 rounded-xl bg-kv-violet/10 px-4 py-3 text-center text-[0.95rem] leading-snug text-kv-ink ring-1 ring-kv-violet/30" aria-live="polite">
            {{ live.text }}
          </p>
        }
      </div>

      <div class="space-y-4 border-t border-kv-border p-5">
        @if (room.audioBlocked()) {
          <button type="button" class="btn w-full bg-amber-400/15 text-amber-200 ring-1 ring-amber-400/30" (click)="room.resumeAudio()">
            <lucide-icon [img]="volumeIcon" [size]="16" /> Activar audio del agente
          </button>
        }

        <div class="flex gap-2">
          @if (!active()) {
            <button type="button" class="btn-primary flex-1 py-3" [disabled]="room.connection() === 'connecting'" (click)="room.start()">
              <lucide-icon [img]="phoneIcon" [size]="18" />
              {{ room.connection() === 'connecting' ? 'Conectando…' : 'Iniciar conversación' }}
            </button>
          } @else {
            <button
              type="button"
              class="btn-ghost"
              [disabled]="room.connection() !== 'connected' || room.mic() === 'denied'"
              [attr.aria-pressed]="room.mic() === 'muted'"
              (click)="room.toggleMute()"
            >
              <lucide-icon [img]="room.mic() === 'on' ? micIcon : micOffIcon" [size]="18" />
              {{ room.mic() === 'on' ? 'Silenciar' : 'Activar micrófono' }}
            </button>
            <button type="button" class="btn-danger flex-1" (click)="room.stop()">
              <lucide-icon [img]="phoneOffIcon" [size]="18" /> Finalizar
            </button>
          }
        </div>

        @if (room.connection() === 'disconnected' || room.connection() === 'error') {
          <button type="button" class="btn-ghost w-full" (click)="room.reconnect()">
            <lucide-icon [img]="retryIcon" [size]="16" /> Reconectar
          </button>
        }

        <app-turn-mode-selector />

        <form class="flex gap-2" (submit)="$event.preventDefault(); send()">
          <label for="kv-text" class="sr-only">Escribe una pregunta</label>
          <input
            id="kv-text"
            class="min-w-0 flex-1 rounded-xl border border-kv-border bg-kv-bg/70 px-3 py-2.5 text-sm text-kv-ink placeholder:text-kv-subtle disabled:opacity-50"
            placeholder="O escribe tu pregunta…"
            autocomplete="off"
            [disabled]="room.connection() !== 'connected'"
            [value]="draft()"
            (input)="draft.set($any($event.target).value)"
          />
          <button type="submit" class="btn-primary !px-3" [disabled]="room.connection() !== 'connected' || !draft().trim()" aria-label="Enviar pregunta escrita">
            <lucide-icon [img]="sendIcon" [size]="16" />
          </button>
        </form>

        @if (room.microphones().length > 1 && active()) {
          <label class="block text-xs font-medium text-kv-muted">
            Micrófono
            <select
              class="mt-1 block w-full rounded-lg border border-kv-border bg-kv-elevated px-3 py-2 text-sm text-kv-ink"
              [value]="room.activeMicId() ?? ''"
              (change)="room.selectMicrophone($any($event.target).value)"
            >
              @for (device of room.microphones(); track device.deviceId) {
                <option [value]="device.deviceId">{{ device.label || 'Micrófono' }}</option>
              }
            </select>
          </label>
        }
      </div>
    </section>
  `,
})
export class VoiceSessionComponent {
  protected readonly room = inject(VoiceRoomService);
  protected readonly store = inject(ConversationStore);
  protected readonly prefs = inject(PreferencesService);

  protected readonly micIcon = Mic;
  protected readonly micOffIcon = MicOff;
  protected readonly phoneIcon = Phone;
  protected readonly phoneOffIcon = PhoneOff;
  protected readonly retryIcon = RotateCw;
  protected readonly volumeIcon = Volume2;
  protected readonly sendIcon = Send;

  protected readonly userSpeaking = signal(false);
  protected readonly draft = signal('');
  protected readonly active = computed(() => ['connected', 'reconnecting'].includes(this.room.connection()));

  protected readonly orbState = computed<OrbState>(() => {
    const connection = this.room.connection();
    if (connection === 'connecting' || connection === 'reconnecting') return 'conectando';
    if (connection === 'error' || connection === 'disconnected') return 'error';
    if (connection !== 'connected') return 'desconectado';
    const activity = this.store.activity();
    if (activity === 'speaking') return 'respondiendo';
    if (activity === 'querying') return 'consultando';
    if (activity === 'thinking') return 'procesando';
    if (this.userSpeaking() && this.room.mic() === 'on') return 'usuario_hablando';
    if (activity === 'waiting') return 'conectando';
    return 'escuchando';
  });
  protected readonly state = computed(() => STATES[this.orbState()]);
  protected readonly orbTone = computed(() => {
    const s = this.orbState();
    if (s === 'error') return 'error' as const;
    return s === 'procesando' || s === 'consultando' ? ('busy' as const) : ('idle' as const);
  });

  protected async send(): Promise<void> {
    if (await this.room.sendText(this.draft())) this.draft.set('');
  }
}
