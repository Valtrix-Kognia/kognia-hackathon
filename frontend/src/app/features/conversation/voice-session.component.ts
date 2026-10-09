import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { LucideAngularModule, Mic, MicOff, Phone, PhoneOff, RotateCw, Volume2 } from 'lucide-angular';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { VoiceRoomService } from '../../core/services/voice-room.service';
import { AgentStatusComponent } from './agent-status.component';
import { AudioVisualizerComponent } from './audio-visualizer.component';

@Component({
  selector: 'app-voice-session',
  imports: [LucideAngularModule, AgentStatusComponent, AudioVisualizerComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card overflow-hidden" aria-labelledby="voice-title">
      <div class="bg-gradient-to-br from-brand-800 via-brand-700 to-brand-600 px-5 pb-5 pt-4 text-white">
        <div class="flex items-center justify-between">
          <h2 id="voice-title" class="text-sm font-semibold tracking-tight text-brand-100">Conversación por voz</h2>
          <span class="chip {{ micChip().tone }}">
            <lucide-icon [img]="micChip().on ? micIcon : micOffIcon" [size]="12" />
            {{ micChip().label }}
          </span>
        </div>
        <div class="mt-3 rounded-xl bg-white/5 px-2 ring-1 ring-white/10">
          <app-audio-visualizer [track]="visualTrack()" [color]="store.activity() === 'speaking' ? '#9fb7ff' : '#ffffff'" />
        </div>
      </div>

      <div class="space-y-4 p-5">
        <app-agent-status [activity]="store.activity()" />

        @if (store.agentLive(); as live) {
          <p class="rounded-xl bg-sky-50 px-3.5 py-2.5 text-sm text-sky-900" aria-live="polite">
            <span class="font-semibold">Kognia:</span> {{ live.text }}
          </p>
        }

        @if (room.audioBlocked()) {
          <button type="button" class="flex w-full items-center justify-center gap-2 rounded-xl bg-amber-100 px-4 py-2.5 text-sm font-medium text-amber-900 hover:bg-amber-200" (click)="room.resumeAudio()">
            <lucide-icon [img]="volumeIcon" [size]="16" /> Activar audio del agente
          </button>
        }

        <div class="flex flex-wrap gap-2">
          @if (!active()) {
            <button
              type="button"
              class="flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-wait disabled:opacity-60"
              [disabled]="room.connection() === 'connecting'"
              (click)="room.start()"
            >
              <lucide-icon [img]="phoneIcon" [size]="18" />
              {{ room.connection() === 'connecting' ? 'Conectando…' : 'Iniciar conversación' }}
            </button>
          } @else {
            <button
              type="button"
              class="flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
              [disabled]="room.connection() !== 'connected' || room.mic() === 'denied'"
              [attr.aria-pressed]="room.mic() === 'muted'"
              (click)="room.toggleMute()"
            >
              <lucide-icon [img]="room.mic() === 'on' ? micIcon : micOffIcon" [size]="18" />
              {{ room.mic() === 'on' ? 'Silenciar' : 'Activar micrófono' }}
            </button>
            <button
              type="button"
              class="flex flex-1 items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-rose-700"
              (click)="room.stop()"
            >
              <lucide-icon [img]="phoneOffIcon" [size]="18" /> Finalizar
            </button>
          }
        </div>

        @if (room.connection() === 'disconnected' || room.connection() === 'error') {
          <button type="button" class="flex w-full items-center justify-center gap-2 rounded-xl border border-brand-200 px-4 py-2.5 text-sm font-medium text-brand-700 hover:bg-brand-50" (click)="room.reconnect()">
            <lucide-icon [img]="retryIcon" [size]="16" /> Reconectar
          </button>
        }

        @if (room.microphones().length > 1 && active()) {
          <label class="block text-xs font-medium text-slate-500">
            Micrófono
            <select
              class="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
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

  protected readonly micIcon = Mic;
  protected readonly micOffIcon = MicOff;
  protected readonly phoneIcon = Phone;
  protected readonly phoneOffIcon = PhoneOff;
  protected readonly retryIcon = RotateCw;
  protected readonly volumeIcon = Volume2;

  protected readonly active = computed(() => ['connected', 'reconnecting'].includes(this.room.connection()));
  protected readonly visualTrack = computed(() =>
    this.store.activity() === 'speaking' ? this.room.agentTrack() : this.room.localTrack(),
  );
  protected readonly micChip = computed(() => {
    switch (this.room.mic()) {
      case 'on':
        return { label: 'Micrófono activo', on: true, tone: 'bg-emerald-400/20 text-emerald-100' };
      case 'requesting':
        return { label: 'Solicitando permiso', on: false, tone: 'bg-amber-400/20 text-amber-100' };
      case 'muted':
        return { label: 'Silenciado', on: false, tone: 'bg-white/10 text-brand-100' };
      case 'denied':
        return { label: 'Permiso denegado', on: false, tone: 'bg-rose-400/25 text-rose-100' };
      case 'unavailable':
        return { label: 'Sin micrófono', on: false, tone: 'bg-rose-400/25 text-rose-100' };
      default:
        return { label: 'Micrófono apagado', on: false, tone: 'bg-white/10 text-brand-100' };
    }
  });
}
