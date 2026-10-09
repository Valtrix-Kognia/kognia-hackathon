import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { CirclePlus, Download, LucideAngularModule } from 'lucide-angular';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { VoiceRoomService } from '../../core/services/voice-room.service';
import { ConnectionStatusComponent } from '../../shared/components/connection-status.component';
import { VoiceSessionComponent } from '../conversation/voice-session.component';
import { SentimentPanelComponent } from '../emotions/sentiment-panel.component';
import { IpsResultsComponent } from '../ips/ips-results.component';
import { LatencyPanelComponent } from '../metrics/latency-panel.component';
import { TranscriptTimelineComponent } from '../transcription/transcript-timeline.component';

@Component({
  selector: 'app-dashboard-page',
  imports: [
    LucideAngularModule,
    DatePipe,
    ConnectionStatusComponent,
    VoiceSessionComponent,
    TranscriptTimelineComponent,
    IpsResultsComponent,
    SentimentPanelComponent,
    LatencyPanelComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="bg-brand-950 text-white">
      <div class="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3.5 sm:px-6">
        <div class="flex items-center gap-2.5">
          <svg viewBox="0 0 32 32" class="size-8" aria-hidden="true">
            <rect width="32" height="32" rx="9" fill="#3b63dd" />
            <path d="M9 9v14M9 16l7-7M9 16l7 7" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" fill="none" />
            <path d="M20 12.5v7M23.5 10v12" stroke="#9fb7ff" stroke-width="2.4" stroke-linecap="round" />
          </svg>
          <div class="leading-tight">
            <h1 class="text-base font-semibold tracking-tight">Kognia Voice</h1>
            <p class="text-xs text-brand-200">IPS de Colombia · datos oficiales</p>
          </div>
        </div>

        <div class="ml-auto flex flex-wrap items-center gap-3">
          <app-connection-status [state]="room.connection()" />
          @if (room.sessionId(); as id) {
            <span class="hidden text-xs text-brand-200 md:inline" [title]="id">
              Sesión {{ shortId() }} · expira {{ room.expiresAt() | date: 'HH:mm' }}
            </span>
          }
          @if (store.sessionInfo(); as info) {
            <span class="hidden text-xs text-brand-300 lg:inline">{{ info.stt }} · {{ info.llm }} · {{ info.tts }}</span>
          }
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-sm font-medium transition hover:bg-white/20 disabled:opacity-50"
            [disabled]="!store.sessionId()"
            (click)="exportSession()"
            title="Descargar transcripción, decisiones y latencias para evaluación"
          >
            <lucide-icon [img]="downloadIcon" [size]="16" /> Exportar
          </button>
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-sm font-medium transition hover:bg-white/20 disabled:opacity-50"
            [disabled]="room.connection() === 'connecting'"
            (click)="room.newSession()"
          >
            <lucide-icon [img]="newIcon" [size]="16" /> Nueva sesión
          </button>
        </div>
      </div>
    </header>

    <main class="mx-auto grid max-w-7xl gap-5 px-4 py-5 sm:px-6 lg:grid-cols-12">
      <div class="space-y-5 lg:col-span-4">
        <app-voice-session />
        <app-sentiment-panel />
      </div>
      <div class="lg:col-span-4 lg:h-[calc(100vh-7.5rem)] lg:min-h-[32rem]">
        <app-transcript-timeline />
      </div>
      <div class="space-y-5 lg:col-span-4">
        <app-ips-results />
        <app-latency-panel />
      </div>
    </main>

    <footer class="mx-auto max-w-7xl px-4 pb-6 text-xs text-slate-400 sm:px-6">
      Fuente única: “Relación de IPS públicas y privadas según el nivel de atención y capacidad instalada”, Ministerio de Salud y
      Protección Social (datos.gov.co, s2ru-bqt6). Las respuestas se generan a partir de consultas en tiempo real a la API oficial.
    </footer>
  `,
})
export class DashboardPageComponent {
  protected readonly room = inject(VoiceRoomService);
  protected readonly store = inject(ConversationStore);
  protected readonly newIcon = CirclePlus;
  protected readonly downloadIcon = Download;

  protected exportSession(): void {
    const blob = new Blob([JSON.stringify(this.store.exportSnapshot(), null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kognia-${this.store.sessionId() ?? 'sesion'}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }
  protected readonly shortId = computed(() => this.room.sessionId()?.slice(-6) ?? '');
}
