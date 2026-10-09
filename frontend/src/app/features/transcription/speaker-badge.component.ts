import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { speakerColor } from '../../shared/utils/labels';

@Component({
  selector: 'app-speaker-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="chip chip-neutral !text-kv-ink" [title]="title()">
      <span class="h-2 w-2 rounded-full" [style.background]="color()" aria-hidden="true"></span>
      {{ label() }}
    </span>
  `,
})
export class SpeakerBadgeComponent {
  readonly label = input.required<string>();
  protected readonly color = computed(() => speakerColor(this.label()));
  protected readonly title = computed(() => {
    const label = this.label();
    if (label === 'Kognia') return 'Agente de voz';
    if (label === 'Hablante desconocido') return 'La diarización no pudo atribuir este segmento con confianza';
    if (label === 'Texto escrito') return 'Mensaje enviado por escrito';
    return 'Voz distinguida por diarización acústica; no identifica a la persona';
  });
}
