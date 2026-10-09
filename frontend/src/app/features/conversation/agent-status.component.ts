import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { AudioLines, Database, Ear, Loader, LucideAngularModule, PowerOff, Sparkles } from 'lucide-angular';
import { AgentActivity } from '../../core/models/voice-session.model';

const META: Record<AgentActivity, { label: string; hint: string; icon: typeof Ear; tone: string }> = {
  offline: { label: 'Inactivo', hint: 'Inicia una sesión para conversar', icon: PowerOff, tone: 'bg-slate-100 text-slate-500' },
  waiting: { label: 'Preparando agente', hint: 'Conectando con Kognia…', icon: Loader, tone: 'bg-amber-50 text-amber-700' },
  listening: { label: 'Escuchando', hint: 'Haz tu pregunta sobre IPS', icon: Ear, tone: 'bg-emerald-50 text-emerald-700' },
  thinking: { label: 'Procesando', hint: 'Interpretando tu pregunta', icon: Sparkles, tone: 'bg-brand-50 text-brand-700' },
  querying: { label: 'Consultando datos', hint: 'API oficial datos.gov.co', icon: Database, tone: 'bg-violet-50 text-violet-700' },
  speaking: { label: 'Respondiendo', hint: 'Puedes interrumpir hablando', icon: AudioLines, tone: 'bg-sky-50 text-sky-700' },
};

@Component({
  selector: 'app-agent-status',
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex items-center gap-3 rounded-xl px-3.5 py-2.5 {{ meta().tone }}" role="status" aria-live="polite">
      <lucide-icon
        [img]="meta().icon"
        [size]="20"
        [class.animate-spin]="activity() === 'waiting'"
        [class.animate-pulse]="activity() === 'thinking' || activity() === 'querying'"
      />
      <div class="leading-tight">
        <p class="text-sm font-semibold">{{ meta().label }}</p>
        <p class="text-xs opacity-80">{{ meta().hint }}</p>
      </div>
    </div>
  `,
})
export class AgentStatusComponent {
  readonly activity = input.required<AgentActivity>();
  protected readonly meta = computed(() => META[this.activity()]);
}
