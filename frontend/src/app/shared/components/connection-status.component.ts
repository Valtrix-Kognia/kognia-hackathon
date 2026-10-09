import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { ConnectionState } from '../../core/models/voice-session.model';

const META: Record<ConnectionState, { label: string; dot: string; chip: string }> = {
  idle: { label: 'Sin conexión', dot: 'bg-slate-400', chip: 'bg-white/10 text-brand-100' },
  connecting: { label: 'Conectando…', dot: 'bg-amber-400 animate-pulse', chip: 'bg-amber-400/15 text-amber-100' },
  connected: { label: 'Conectado', dot: 'bg-emerald-400', chip: 'bg-emerald-400/15 text-emerald-100' },
  reconnecting: { label: 'Reconectando…', dot: 'bg-amber-400 animate-pulse', chip: 'bg-amber-400/15 text-amber-100' },
  disconnected: { label: 'Desconectado', dot: 'bg-rose-400', chip: 'bg-rose-400/15 text-rose-100' },
  error: { label: 'Error de conexión', dot: 'bg-rose-400', chip: 'bg-rose-400/15 text-rose-100' },
};

@Component({
  selector: 'app-connection-status',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="chip {{ meta().chip }}" role="status" aria-live="polite">
      <span class="size-2 rounded-full {{ meta().dot }}"></span>
      {{ meta().label }}
    </span>
  `,
})
export class ConnectionStatusComponent {
  readonly state = input.required<ConnectionState>();
  protected readonly meta = computed(() => META[this.state()]);
}
