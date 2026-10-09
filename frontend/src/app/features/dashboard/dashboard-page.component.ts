import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import {
  AArrowDown,
  AArrowUp,
  Captions,
  ChartBar,
  CirclePlus,
  Download,
  FileSearch,
  Gauge,
  LucideAngularModule,
  Map as MapIcon,
  MessageSquareText,
  Mic,
  MicOff,
  Settings2,
} from 'lucide-angular';
import { ConversationStore } from '../../core/services/conversation-store.service';
import { AnalysisTab, DashboardStateService } from '../../core/services/dashboard-state.service';
import { PreferencesService } from '../../core/services/preferences.service';
import { VoiceRoomService } from '../../core/services/voice-room.service';
import { ConnectionStatusComponent } from '../../shared/components/connection-status.component';
import { VoiceSessionComponent } from '../conversation/voice-session.component';
import { SentimentPanelComponent } from '../emotions/sentiment-panel.component';
import { EvidencePanelComponent } from '../evidence/evidence-panel.component';
import { MapPanelComponent } from '../map/map-panel.component';
import { LatencyPanelComponent } from '../metrics/latency-panel.component';
import { TranscriptTimelineComponent } from '../transcription/transcript-timeline.component';
import { VisualizationPanelComponent } from '../viz/visualization-panel.component';

type MobileView = 'voz' | 'transcripcion' | 'datos';

const AGENT_LABELS: Record<string, string> = {
  offline: 'Agente inactivo',
  waiting: 'Agente conectándose',
  listening: 'Agente escuchando',
  thinking: 'Agente procesando',
  querying: 'Consultando datos',
  speaking: 'Agente hablando',
};

@Component({
  selector: 'app-dashboard-page',
  imports: [
    LucideAngularModule,
    DatePipe,
    ConnectionStatusComponent,
    VoiceSessionComponent,
    TranscriptTimelineComponent,
    VisualizationPanelComponent,
    EvidencePanelComponent,
    MapPanelComponent,
    SentimentPanelComponent,
    LatencyPanelComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a href="#kv-main" class="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-kv-primary focus:px-3 focus:py-2">Saltar al contenido</a>

    <header class="sticky top-0 z-30 border-b border-kv-border bg-kv-bg/85 backdrop-blur">
      <div class="mx-auto flex max-w-[1680px] flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3 sm:px-6">
        <div class="flex items-center gap-2.5">
          <svg viewBox="0 0 32 32" class="size-9" aria-hidden="true">
            <defs><linearGradient id="kv-logo" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3b82f6" /><stop offset="1" stop-color="#8b5cf6" /></linearGradient></defs>
            <rect width="32" height="32" rx="9" fill="url(#kv-logo)" />
            <path d="M9 9v14M9 16l7-7M9 16l7 7" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" fill="none" />
            <path d="M20 12.5v7M23.5 10v12" stroke="#22d3ee" stroke-width="2.4" stroke-linecap="round" />
          </svg>
          <div class="leading-tight">
            <h1 class="text-base font-semibold tracking-tight">Kognia Voice</h1>
            <p class="text-[11px] text-kv-muted">IPS de Colombia · datos oficiales en tiempo real</p>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2" aria-label="Estado del sistema">
          <app-connection-status [state]="room.connection()" />
          <span class="chip chip-neutral" role="status">{{ agentLabel() }}</span>
          <span class="chip chip-neutral" role="status">
            <lucide-icon [img]="room.mic() === 'on' ? micIcon : micOffIcon" [size]="12" />
            {{ micLabel() }}
          </span>
          @if (room.sessionId(); as id) {
            <span class="hidden text-[11px] text-kv-subtle xl:inline" [title]="id">Sesión {{ id.slice(-6) }} · expira {{ room.expiresAt() | date: 'HH:mm' }}</span>
          }
        </div>

        <div class="ml-auto flex items-center gap-2">
          @if (!active()) {
            <button type="button" class="btn-primary !py-2" [disabled]="room.connection() === 'connecting'" (click)="room.start()">Iniciar sesión de voz</button>
          } @else {
            <button type="button" class="btn-danger !py-2" (click)="room.stop()">Finalizar</button>
          }
          <button type="button" class="btn-ghost !px-3 !py-2" [disabled]="room.connection() === 'connecting'" (click)="room.newSession()" title="Nueva sesión" aria-label="Nueva sesión">
            <lucide-icon [img]="newIcon" [size]="16" /><span class="hidden md:inline">Nueva</span>
          </button>
          <button type="button" class="btn-ghost !px-3 !py-2" [disabled]="!store.sessionId()" (click)="exportSession()" title="Descargar transcripción, decisiones y latencias" aria-label="Exportar sesión">
            <lucide-icon [img]="downloadIcon" [size]="16" /><span class="hidden md:inline">Exportar</span>
          </button>
          <div class="relative">
            <button
              type="button"
              class="btn-ghost !px-3 !py-2"
              [attr.aria-expanded]="settingsOpen()"
              aria-controls="kv-settings"
              aria-label="Configuración y accesibilidad"
              (click)="settingsOpen.set(!settingsOpen())"
            >
              <lucide-icon [img]="settingsIcon" [size]="16" />
            </button>
            @if (settingsOpen()) {
              <div id="kv-settings" class="fade-in absolute right-0 top-12 z-40 w-72 rounded-xl border border-kv-border bg-kv-elevated p-4 shadow-2xl" role="dialog" aria-label="Configuración y accesibilidad" (keydown.escape)="settingsOpen.set(false)">
                <p class="eyebrow">Tamaño de texto</p>
                <div class="mt-2 flex items-center gap-2">
                  <button type="button" class="btn-ghost !px-3 !py-1.5" aria-label="Reducir texto" (click)="prefs.stepFont(-1)"><lucide-icon [img]="smallerIcon" [size]="16" /></button>
                  <span class="tabular flex-1 text-center text-sm">{{ fontPercent() }} %</span>
                  <button type="button" class="btn-ghost !px-3 !py-1.5" aria-label="Aumentar texto" (click)="prefs.stepFont(1)"><lucide-icon [img]="largerIcon" [size]="16" /></button>
                </div>
                <label class="mt-4 flex cursor-pointer items-center justify-between gap-3 text-sm">
                  <span class="flex items-center gap-2"><lucide-icon [img]="captionsIcon" [size]="16" /> Subtítulos de Kognia</span>
                  <input type="checkbox" class="h-4 w-4 accent-[var(--kv-accent)]" [checked]="prefs.captions()" (change)="prefs.captions.set($any($event.target).checked)" />
                </label>
                <p class="mt-4 text-[11px] text-kv-subtle">Las animaciones se reducen automáticamente si tu sistema lo solicita.</p>
              </div>
            }
          </div>
        </div>
      </div>
    </header>

    <main id="kv-main" class="mx-auto grid max-w-[1680px] gap-5 px-4 pb-24 pt-5 sm:px-6 lg:grid-cols-12 lg:pb-8">
      <div class="space-y-5 lg:col-span-4 lg:block xl:col-span-3" [class.hidden]="mobileView() !== 'voz'">
        <app-voice-session />
      </div>

      <section class="card min-w-0 lg:col-span-8 lg:block xl:col-span-6" [class.hidden]="mobileView() !== 'datos'" aria-label="Análisis de datos">
        <div class="flex flex-wrap items-center gap-1 border-b border-kv-border p-2" role="tablist" aria-label="Paneles de análisis">
          @for (tab of tabs; track tab.id) {
            <button
              type="button"
              role="tab"
              class="tab flex items-center gap-1.5"
              [class.tab-active]="dashboard.activeTab() === tab.id"
              [attr.aria-selected]="dashboard.activeTab() === tab.id"
              [attr.aria-controls]="'panel-' + tab.id"
              [id]="'tab-' + tab.id"
              (click)="dashboard.activeTab.set(tab.id)"
            >
              <lucide-icon [img]="tab.icon" [size]="15" /> {{ tab.label }}
              @if (tab.id === 'visualizacion' && store.runningQueries() > 0) {
                <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-kv-violet" aria-label="consulta en curso"></span>
              }
            </button>
          }
        </div>
        <div class="p-5" role="tabpanel" [id]="'panel-' + dashboard.activeTab()" [attr.aria-labelledby]="'tab-' + dashboard.activeTab()">
          @switch (dashboard.activeTab()) {
            @case ('visualizacion') { <app-visualization-panel /> }
            @case ('mapa') {
              @defer {
                <app-map-panel />
              } @placeholder (minimum 150ms) {
                <div class="skeleton aspect-[7/8] w-full max-w-xl"></div>
              } @error {
                <p role="alert" class="text-sm text-red-200">No se pudo cargar el módulo del mapa.</p>
              }
            }
            @case ('evidencia') { <app-evidence-panel /> }
            @case ('analisis') {
              <div class="grid gap-5 xl:grid-cols-2">
                <app-sentiment-panel />
                <app-latency-panel />
              </div>
            }
          }
        </div>
      </section>

      <div class="min-w-0 lg:col-span-12 lg:block xl:col-span-3 xl:h-[calc(100vh-6.5rem)] xl:min-h-[34rem]" [class.hidden]="mobileView() !== 'transcripcion'">
        <app-transcript-timeline />
      </div>
    </main>

    <nav class="fixed inset-x-0 bottom-0 z-30 grid grid-cols-3 border-t border-kv-border bg-kv-bg/95 backdrop-blur lg:hidden" aria-label="Secciones">
      @for (view of mobileViews; track view.id) {
        <button
          type="button"
          class="flex flex-col items-center gap-0.5 py-2.5 text-[11px]"
          [class.text-kv-accent]="mobileView() === view.id"
          [class.text-kv-muted]="mobileView() !== view.id"
          [attr.aria-current]="mobileView() === view.id ? 'page' : null"
          (click)="mobileView.set(view.id)"
        >
          <lucide-icon [img]="view.icon" [size]="18" /> {{ view.label }}
        </button>
      }
    </nav>

    <footer class="mx-auto hidden max-w-[1680px] px-6 pb-6 text-[11px] text-kv-subtle lg:block">
      Fuente única: “Relación de IPS públicas y privadas según el nivel de atención y capacidad instalada”, Ministerio de Salud y Protección
      Social (datos.gov.co, s2ru-bqt6). Límites departamentales: geoBoundaries / OpenStreetMap (ODbL 1.0).
    </footer>
  `,
})
export class DashboardPageComponent {
  protected readonly room = inject(VoiceRoomService);
  protected readonly store = inject(ConversationStore);
  protected readonly dashboard = inject(DashboardStateService);
  protected readonly prefs = inject(PreferencesService);

  protected readonly newIcon = CirclePlus;
  protected readonly downloadIcon = Download;
  protected readonly settingsIcon = Settings2;
  protected readonly micIcon = Mic;
  protected readonly micOffIcon = MicOff;
  protected readonly smallerIcon = AArrowDown;
  protected readonly largerIcon = AArrowUp;
  protected readonly captionsIcon = Captions;

  protected readonly settingsOpen = signal(false);
  protected readonly mobileView = signal<MobileView>('voz');

  protected readonly tabs: { id: AnalysisTab; label: string; icon: typeof ChartBar }[] = [
    { id: 'visualizacion', label: 'Visualización', icon: ChartBar },
    { id: 'mapa', label: 'Mapa', icon: MapIcon },
    { id: 'evidencia', label: 'Evidencia', icon: FileSearch },
    { id: 'analisis', label: 'Análisis', icon: Gauge },
  ];
  protected readonly mobileViews: { id: MobileView; label: string; icon: typeof ChartBar }[] = [
    { id: 'voz', label: 'Voz', icon: Mic },
    { id: 'transcripcion', label: 'Transcripción', icon: MessageSquareText },
    { id: 'datos', label: 'Datos y mapa', icon: ChartBar },
  ];

  protected readonly active = computed(() => ['connected', 'reconnecting'].includes(this.room.connection()));
  protected readonly agentLabel = computed(() => AGENT_LABELS[this.store.activity()] ?? 'Agente');
  protected readonly fontPercent = computed(() => Math.round(this.prefs.fontScale() * 100));
  protected readonly micLabel = computed(() => {
    switch (this.room.mic()) {
      case 'on':
        return 'Micrófono activo';
      case 'muted':
        return 'Silenciado';
      case 'denied':
        return 'Permiso denegado';
      case 'requesting':
        return 'Solicitando permiso';
      case 'unavailable':
        return 'Sin micrófono';
      default:
        return 'Micrófono apagado';
    }
  });

  protected exportSession(): void {
    const blob = new Blob([JSON.stringify(this.store.exportSnapshot(), null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kognia-${this.store.sessionId() ?? 'sesion'}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }
}
